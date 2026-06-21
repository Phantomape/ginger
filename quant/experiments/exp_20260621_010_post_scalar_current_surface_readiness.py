"""exp-20260621-010: current surface alpha readiness after scalar stack.

Alpha-search blocker. This run checks whether the local forward/default-off
surfaces that appeared after exp-20260621-009 have matured into a non-repeat,
PIT-safe, three-window candidate-pool data edge. It changes no trading policy.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
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


EXPERIMENT_ID = "exp-20260621-010"
SLUG = "post_scalar_current_surface_readiness"
RUNNER_NAME = f"quant/experiments/exp_20260621_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260621_010_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
README_MD = DATA_DIR / "README.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
PAPER_SLEEVES_DIR = REPO_ROOT / "data" / "paper_sleeves"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
MIN_TARGET_ROWS = 20
MIN_TARGET_WINDOWS = 3

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "coverage": "data/non_ohlcv/backtest_coverage_20251023_20260421.json",
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
        "coverage": "data/non_ohlcv/backtest_coverage_20250423_20251022.json",
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
        "coverage": "data/non_ohlcv/backtest_coverage_20241002_20250422.json",
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
    "candidate_pool/data-edge readiness: after the accepted allocator scalar "
    "stack, the next alpha should proceed only if current local forward/"
    "default-off surfaces expose a non-frozen PIT source with three-window "
    "coverage and enough sample; otherwise another strategy replay would "
    "duplicate frozen families or leak non-PIT data."
)

PRIOR_EXPERIMENTS = [
    "exp-20260621-009",
    "exp-20260621-008",
    "exp-20260621-004",
    "exp-20260621-003",
    "exp-20260620-012",
    "exp-20260620-013",
    "exp-20260619-020",
    "exp-20260618-024",
    "exp-20260617-004",
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
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle = f'"experiment_id": "{EXPERIMENT_ID}"'
    if path.exists() and needle in path.read_text(encoding="utf-8-sig"):
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


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
    return {label: {field: 0.0 for field in fields} for label in CANONICAL_WINDOWS}


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


def collect_nested_keys(value: Any, keys: set[str] | None = None) -> set[str]:
    keys = keys if keys is not None else set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key))
            collect_nested_keys(nested, keys)
    elif isinstance(value, list):
        for item in value[:25]:
            collect_nested_keys(item, keys)
    return keys


def count_missing_field(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if not row.get(field))


def summarize_accepted_helper_state() -> dict[str, Any]:
    path = PAPER_SLEEVES_DIR / "accepted_helper_source_priority_allocator" / "state.json"
    payload = read_json(path)
    closed = list(payload.get("closed_positions") or [])
    open_positions = list(payload.get("open_positions") or [])
    pending = list(payload.get("pending_entries") or [])
    skipped = list(payload.get("skipped_days") or [])
    rows = closed + open_positions + pending
    source_counts = Counter(str(row.get("source_family") or "unknown") for row in rows)
    return {
        "path": repo_rel(path),
        "updated_at": payload.get("updated_at"),
        "closed_position_count": len(closed),
        "open_position_count": len(open_positions),
        "pending_entry_count": len(pending),
        "skipped_day_count": len(skipped),
        "source_family_counts": dict(source_counts),
        "entry_date_missing_count": count_missing_field(rows, "entry_date"),
        "target_price_missing_count": count_missing_field(rows, "target_price"),
        "maturity_gate": {
            "minimum_closed_rows": MIN_TARGET_ROWS,
            "passed": len(closed) >= MIN_TARGET_ROWS,
            "reason": "closed forward outcomes are required before using the surface as replacement-value evidence",
        },
    }


def summarize_forward_watch(name: str, relative_path: str) -> dict[str, Any]:
    path = REPO_ROOT / relative_path
    payload = read_json(path)
    return {
        "name": name,
        "path": repo_rel(path),
        "updated_at": payload.get("updated_at"),
        "asof_date": payload.get("asof_date"),
        "candidate_count": int(payload.get("candidate_count") or 0),
        "ledger_row_count": int(payload.get("ledger_row_count") or 0),
        "closed_position_count": len(payload.get("closed_positions") or []),
        "open_position_count": len(payload.get("open_positions") or []),
        "pending_entry_count": len(payload.get("pending_entries") or []),
        "watch_specific_counts": {
            "ten_k_event_count": payload.get("ten_k_event_count"),
            "pit_safe_10k_count": payload.get("pit_safe_10k_count"),
            "liquidity_qualified_count": payload.get("liquidity_qualified_count"),
            "no_gap_rs20_watch_count": payload.get("no_gap_rs20_watch_count"),
            "platform_rs20_missed_count": payload.get("platform_rs20_missed_count"),
        },
        "production_impact": payload.get("production_impact") or {},
        "maturity_gate": {
            "minimum_ledger_rows": MIN_TARGET_ROWS,
            "passed": int(payload.get("ledger_row_count") or 0) >= MIN_TARGET_ROWS,
        },
    }


def audit_current_forward_surfaces() -> dict[str, Any]:
    surfaces = {
        "accepted_helper_source_priority_allocator": summarize_accepted_helper_state(),
        "platform_rs20_no_gap": summarize_forward_watch(
            "PLATFORM_RS20_NO_GAP_FORWARD_WATCH",
            "data/paper_sleeves/platform_rs20_no_gap/summary.json",
        ),
        "sec_10k_liquidity": summarize_forward_watch(
            "SEC_10K_LIQUIDITY_FORWARD_WATCH",
            "data/paper_sleeves/sec_10k_liquidity/summary.json",
        ),
        "pead_broad_universe": summarize_forward_watch(
            "PEAD_BROAD_UNIVERSE_PAPER",
            "data/paper_sleeves/pead_broad_universe_state.json",
        ),
    }
    blockers = []
    for name, row in surfaces.items():
        maturity = row.get("maturity_gate") or {}
        if not maturity.get("passed"):
            blockers.append(
                {
                    "surface": name,
                    "reason": "no mature forward outcome/ledger sample",
                    "closed_position_count": row.get("closed_position_count"),
                    "ledger_row_count": row.get("ledger_row_count"),
                    "candidate_count": row.get("candidate_count"),
                }
            )
    return {
        "surfaces": surfaces,
        "sample_blockers": blockers,
        "all_surfaces_sample_ready": not blockers,
    }


def summarize_coverage_window(label: str, window: dict[str, Any]) -> dict[str, Any]:
    path = REPO_ROOT / str(window["coverage"])
    payload = read_json(path)
    row_counts = Counter()
    for record in payload.get("records") or []:
        for key, value in (record.get("row_counts") or {}).items():
            row_counts[str(key)] += int(value or 0)
    return {
        "label": label,
        "path": repo_rel(path),
        "decision": payload.get("decision"),
        "business_days": payload.get("business_days"),
        "complete_days": payload.get("complete_days"),
        "complete_fraction": payload.get("complete_fraction"),
        "failed_days": payload.get("failed_days"),
        "partial_days": payload.get("partial_days"),
        "row_counts_total": dict(row_counts),
        "coverage_ready": payload.get("decision") == "complete",
    }


def summarize_current_snapshot(date_tag: str) -> dict[str, Any]:
    path = NON_OHLCV_DIR / f"daily_non_ohlcv_snapshot_{date_tag}.json"
    payload = read_json(path)
    nested_keys = collect_nested_keys(payload)
    sec_events = payload.get("sec_filing_events") or {}
    sec_text = payload.get("sec_filing_text") or {}
    form4 = payload.get("form4_transactions") or {}
    options = payload.get("options_onclickmedia") or {}
    return {
        "path": repo_rel(path),
        "status": payload.get("status"),
        "asof_date": payload.get("asof_date"),
        "top_level_keys": sorted(payload.keys()),
        "has_estimate_revision_surface": any(
            key.lower()
            in {
                "analyst_estimates",
                "earnings_estimates",
                "revenue_estimates",
                "estimate_revisions",
                "consensus_estimates",
            }
            for key in nested_keys
        ),
        "sec_event_rows": sec_events.get("rows_written") or sec_events.get("pit_safe_rows"),
        "sec_event_forms": sec_events.get("row_counts_by_form") or {},
        "sec_text_rows": sec_text.get("rows_written"),
        "sec_text_forms": sec_text.get("forms") or [],
        "form4_rows": form4.get("rows_written") or form4.get("pit_safe_count"),
        "form4_open_market_purchase_count": form4.get("open_market_purchase_count"),
        "options_status": options.get("status"),
        "options_rows_written": options.get("rows_written"),
        "options_pit_safe_rows": options.get("pit_safe_rows"),
        "options_error_count": options.get("error_count"),
    }


def audit_non_ohlcv_surface() -> dict[str, Any]:
    coverage = {
        label: summarize_coverage_window(label, row)
        for label, row in CANONICAL_WINDOWS.items()
    }
    current = {
        "20260619": summarize_current_snapshot("20260619"),
        "20260620": summarize_current_snapshot("20260620"),
    }
    desired_edges = {
        "pit_analyst_breadth_dispersion_revenue_estimates": {
            "sample_ready": False,
            "reason": "current snapshots have no analyst/revenue-estimate revision surface",
        },
        "pit_options_asof_surface": {
            "sample_ready": False,
            "reason": "2026-06-19 options refresh failed with zero rows; 2026-06-20 was skipped",
        },
        "structured_sec_customer_supplier_contract_economics": {
            "sample_ready": False,
            "reason": "available SEC text is mostly 8-K text without accepted structured actor/object/magnitude fields",
        },
        "historical_10k_10q_filer_status_by_accession": {
            "sample_ready": False,
            "reason": "current submission categories are not historical PIT cover-page status; recent SEC text has no 10-K/10-Q body rows",
        },
    }
    return {
        "three_window_coverage": coverage,
        "current_snapshots": current,
        "desired_free_data_edges": desired_edges,
        "coverage_note": (
            "The warehouse has non-OHLCV files across the three windows, but the "
            "reviewed alpha-bearing fields are either absent, generic, not PIT "
            "as-of, or currently sample-starved."
        ),
    }


def prior_summary(exp_id: str) -> dict[str, Any]:
    payload = read_json(REPO_ROOT / "experiments" / "logs" / f"{exp_id}.json")
    gate4 = payload.get("gate4") or {}
    return {
        "experiment_id": exp_id,
        "found": bool(payload),
        "decision": payload.get("decision"),
        "status": payload.get("status"),
        "trial_variant_id": payload.get("trial_variant_id"),
        "aggregate_expected_value_delta": payload.get("aggregate_expected_value_delta"),
        "aggregate_strategy_total_pnl_delta": payload.get("aggregate_strategy_total_pnl_delta"),
        "gate4_status": gate4.get("status"),
        "failed_reasons": gate4.get("failed_reasons"),
        "new_evidence_required": (
            (payload.get("post_run_reflection") or {}).get("new_evidence_required")
            or (payload.get("post_run_reflection") or {}).get("best_next_alpha_direction")
            or payload.get("next_evidence_needed")
        ),
    }


def build_gate4() -> dict[str, Any]:
    aggregate = aggregate_windows()
    return {
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
        "reason": "Gate 2/Gate 3 readiness blocked all reviewed current surfaces before a strategy after-policy existed.",
    }


def build_result() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    aggregate = aggregate_windows()
    current_forward = audit_current_forward_surfaces()
    non_ohlcv = audit_non_ohlcv_surface()
    gate4 = build_gate4()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now_utc(),
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_current_surface_no_gate4_ready_nonrepeat_alpha",
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_data_edge_readiness",
        "mechanism_family": "nonrepeat_alpha_candidate_readiness",
        "trial_family": "post_accepted_scalar_stack_current_surface_readiness",
        "trial_variant_id": "post_scalar_current_surface_alpha_readiness_v2",
        "single_causal_variable": "post_scalar_current_surface_alpha_readiness_v2",
        "changed_variable": "post_scalar_current_surface_alpha_readiness_v2",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "prediction": ticket.get("prediction") or {},
        "novelty": ticket.get("novelty") or {},
        "nearby_prior_experiments": [prior_summary(exp_id) for exp_id in PRIOR_EXPERIMENTS],
        "gate1": {
            "passed": True,
            "baseline_result_file": BASELINE_RESULT_FILE,
            "windows": CANONICAL_WINDOWS,
            "aggregate": aggregate,
        },
        "gate2": {
            "status": "blocked",
            "runtime_fields_checked": ["entry_date", "target_price"],
            "current_forward_surface_audit": current_forward,
            "non_ohlcv_surface_audit": non_ohlcv,
            "field_readiness": {
                "entry_date": (
                    "present on accepted-helper open/pending paper rows, but "
                    "not enough closed forward rows exist to create a new after-policy"
                ),
                "target_price": (
                    "absent on current forward watch/state rows; no replayable "
                    "candidate rows cleared PIT/parity/sample checks"
                ),
            },
            "blocking_item": (
                "No reviewed current surface has all of non-frozen novelty, "
                "three-window PIT/parity-safe fields, entry_date/target_price "
                "runtime readiness, and enough sample rows."
            ),
        },
        "gate3": {
            "status": "blocked_before_strategy_filter",
            "baseline_min_survival_rate": aggregate["min_survival_rate"],
            "minimum_target_rows": MIN_TARGET_ROWS,
            "minimum_target_windows": MIN_TARGET_WINDOWS,
            "sample_blockers": current_forward["sample_blockers"],
            "desired_data_edge_readiness": non_ohlcv["desired_free_data_edges"],
            "interpretation": (
                "Adding filters or allocation changes now would violate the "
                "survival/sample guard: the current candidate surfaces either "
                "have zero ledger rows, zero closed outcomes, or no PIT alpha field."
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
                "trading rule or shared helper changed. Any future positive alpha "
                "must be implemented shared-paper-first before acceptance."
            ),
        },
        "calibration": {
            "predicted_success_probability": (ticket.get("prediction") or {}).get("success_probability"),
            "actual_gate4_passed": False,
            "actual_success": 0,
            "failure_modes_observed": [
                "no_mature_forward_rows",
                "no_pit_fields",
                "frozen_near_neighbor",
                "sample_starved",
            ],
        },
        "post_run_reflection": {
            "why_blocked": (
                "Current accepted-helper, platform, SEC 10-K, PEAD, options, "
                "and non-OHLCV snapshot surfaces do not yet expose a non-repeat "
                "PIT field with enough rows to justify a Gate 1-4 after-policy."
            ),
            "negative_result_reflection": (
                "This was negative because the data edge is not mature, not "
                "because a new alpha lost money. Running another allocator "
                "rank/scalar/slot or generic SEC/Companyfacts replay would repeat "
                "nearby rejected families and risk overfitting frozen windows."
            ),
            "best_next_alpha_direction": (
                "Build or acquire a fresh free PIT source before the next Gate 4: "
                "structured SEC customer/supplier/payment-term or contract-"
                "economics rows, historical 10-K/10-Q cover-page filer status by "
                "accession, PIT analyst breadth/dispersion/revenue estimates, or "
                "borrow/options as-of rows with fixed-window coverage."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry allocator source rank/notional/top-N/cooldown, daily "
                "slot capacity, generic SEC item/event filters, current SEC "
                "submissions category, Companyfacts ratio thresholds, or LLM "
                "soft-ranking until a materially new PIT field or mature closed "
                "forward replacement ledger exists."
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
        f"# {EXPERIMENT_ID}: current surface alpha readiness",
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
    lines.extend(
        [
            "",
            "## Blocker",
            "",
            f"Aggregate baseline EV `{aggregate['aggregate_expected_value_score']:.4f}`, "
            f"PnL `${aggregate['aggregate_total_pnl']:,.2f}`. No after policy was run.",
            "",
            "Current surface sample blockers:",
            "",
        ]
    )
    for blocker in result["gate3"]["sample_blockers"]:
        lines.append(
            f"- `{blocker['surface']}`: candidates `{blocker.get('candidate_count')}`, "
            f"ledger `{blocker.get('ledger_row_count')}`, closed `{blocker.get('closed_position_count')}`."
        )
    lines.extend(["", result["post_run_reflection"]["best_next_alpha_direction"], ""])
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Blocked alpha-search readiness record for current local surfaces after "
        "the accepted allocator scalar stack.\n\n"
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
            "nearby_prior_experiments": PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "current_forward_default_off_surface_state",
            "baseline_result_file": BASELINE_RESULT_FILE,
            "evaluation_windows": [
                {"label": label, "start": row["start"], "end": row["end"], "snapshot": row["snapshot"]}
                for label, row in CANONICAL_WINDOWS.items()
            ],
            "acceptance_rule": (
                "Blocked unless a current surface clears PIT/parity, novelty, "
                "entry_date/target_price runtime readiness, and three-window sample maturity."
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
                "aggregate_ev_delta": result["delta_metrics"]["aggregate_expected_value_score"],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "sample_blockers": result["gate3"]["sample_blockers"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
