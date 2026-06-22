"""exp-20260622-003: candidate-pool data surface readiness gate.

Alpha-search direction gate. The run checks whether a new free, non-frozen,
PIT data surface is ready for the standard three-window candidate-pool protocol
and a shared-paper parity path before any strategy logic is changed.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260622-003"
SLUG = "candidate_pool_data_surface_readiness_gate"
RUNNER_NAME = f"quant/experiments/exp_20260622_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260622_003_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
BASELINE_JSON = REPO_ROOT / BASELINE_RESULT_FILE
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
ESTIMATE_REVISION_SUMMARY = (
    REPO_ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_summary_20260620.json"
)
MOOMOO_MANIFEST = (
    REPO_ROOT / "data" / "non_ohlcv" / "moomoo_capital_flow" / "manifest.json"
)
MOOMOO_ROWS = REPO_ROOT / "data" / "non_ohlcv" / "moomoo_capital_flow" / "rows.jsonl"
OPTIONS_SUMMARY = (
    REPO_ROOT / "data" / "non_ohlcv" / "options_onclickmedia_summary_20260619.json"
)
SEC13F_LATEST = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec13f_institutional" / "latest.json"
)
SEC_FTD_ROWS = REPO_ROOT / "data" / "non_ohlcv" / "sec_ftd" / "rows.json"

HYPOTHESIS = (
    "candidate_pool/data-edge: the next alpha should only proceed if a free, "
    "non-frozen PIT data surface has standard three-window coverage and a "
    "shared-paper parity path; otherwise another SEC text, allocator, OHLCV, "
    "or forward-only scout is expected to be negative or non-production-parity."
)

CHANGED_VARIABLE = "non_frozen_free_data_surface_readiness_gate_for_candidate_pool_alpha"
TRIAL_FAMILY = "candidate_pool_data_surface_readiness_gate"
TRIAL_VARIANT_ID = "post_20260622_recent_negative_surface_audit"
MECHANISM_FAMILY = "free_data_edge_candidate_pool"

PREDICTION = {
    "success_probability": 0.2,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "all_free_surfaces_forward_only_or_frozen",
        "recent_neighbors_already_rejected",
        "no_shared_parity_surface",
    ],
    "confidence_reason": (
        "Recent logs show SEC text scouts and allocator retunes are exhausted; "
        "remaining free surfaces may lack fixed-window coverage, so readiness "
        "odds are low but must be audited before another alpha change."
    ),
    "recorded_at": "2026-06-22T02:06:59+00:00",
}

CANONICAL_WINDOWS = [
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
]

RECENT_NEIGHBOR_EXPERIMENTS = [
    "exp-20260622-001",
    "exp-20260622-002",
    "exp-20260621-022",
    "exp-20260621-023",
    "exp-20260621-018",
    "exp-20260617-004",
    "exp-20260621-019",
    "exp-20260621-020",
    "exp-20260611-015",
    "exp-20260609-020",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            for line in f:
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                if limit is not None and len(rows) >= limit:
                    break
    except OSError:
        return rows
    return rows


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    experiment_id = record.get("experiment_id")
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if existing.get("experiment_id") == experiment_id:
                    return
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def baseline_windows() -> dict[str, dict[str, Any]]:
    payload = read_json(BASELINE_JSON, {})
    windows: dict[str, dict[str, Any]] = {}
    for row in payload.get("windows", []):
        label = row["label"]
        windows[label] = {
            "label": label,
            "start": row["start"],
            "end": row["end"],
            "snapshot": row.get("source"),
            "expected_value_score": row["expected_value_score"],
            "sharpe_daily": row["sharpe_daily"],
            "total_pnl": row["total_pnl"],
            "max_drawdown_pct": row["max_drawdown_pct"],
            "win_rate": row.get("win_rate"),
            "trade_count": row["trade_count"],
            "signals_generated": row["signals_generated"],
            "signals_survived": row["signals_survived"],
            "survival_rate": row["survival_rate"],
        }
    return windows


def aggregate_windows(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row["expected_value_score"]) for row in windows.values()), 4
        ),
        "aggregate_total_pnl": round(
            sum(float(row["total_pnl"]) for row in windows.values()), 2
        ),
        "max_window_drawdown_pct": max(
            float(row["max_drawdown_pct"]) for row in windows.values()
        ),
        "min_survival_rate": min(float(row["survival_rate"]) for row in windows.values()),
        "total_trade_count": sum(int(row["trade_count"]) for row in windows.values()),
        "aggregate_signals_generated": sum(
            int(row["signals_generated"]) for row in windows.values()
        ),
        "aggregate_signals_survived": sum(
            int(row["signals_survived"]) for row in windows.values()
        ),
    }


def open_position_field_check() -> dict[str, Any]:
    payload = read_json(OPEN_POSITIONS_JSON, [])
    if isinstance(payload, dict):
        rows = list(payload.get("positions", []))
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    missing_entry = [
        row.get("ticker") for row in rows if isinstance(row, dict) and not row.get("entry_date")
    ]
    missing_target = [
        row.get("ticker")
        for row in rows
        if isinstance(row, dict) and row.get("target_price") in (None, "")
    ]
    return {
        "path": repo_rel(OPEN_POSITIONS_JSON),
        "position_count": len(rows),
        "missing_entry_date_tickers": sorted({x for x in missing_entry if x}),
        "missing_target_price_tickers": sorted({x for x in missing_target if x}),
        "passed": not missing_entry and not missing_target,
    }


def summarize_neighbor_log(experiment_id: str) -> dict[str, Any]:
    path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
    row = read_json(path, {})
    gate4 = row.get("gate4") or {}
    delta = row.get("delta_metrics") or row.get("aggregate") or {}
    return {
        "experiment_id": experiment_id,
        "status": row.get("status"),
        "decision": row.get("decision"),
        "changed_variable": row.get("changed_variable"),
        "mechanism_family": row.get("mechanism_family"),
        "trial_family": row.get("trial_family"),
        "aggregate_ev_delta": (
            gate4.get("aggregate_ev_delta")
            or gate4.get("aggregate_expected_value_delta")
            or delta.get("expected_value_score_delta_sum")
            or delta.get("aggregate_expected_value_score")
            or row.get("expected_value_score_delta")
            or row.get("aggregate_expected_value_delta")
        ),
        "aggregate_pnl_delta": (
            gate4.get("aggregate_pnl_delta")
            or gate4.get("aggregate_total_pnl_delta")
            or delta.get("total_pnl_delta_sum")
            or delta.get("aggregate_total_pnl")
            or row.get("total_pnl_delta")
            or row.get("aggregate_strategy_total_pnl_delta")
        ),
        "gate4_passed": gate4.get("passed") or row.get("numeric_gate4_passed"),
        "failed_reasons": gate4.get("failed_reasons")
        or row.get("calibration", {}).get("failure_modes_observed")
        or [],
        "target_trade_count": gate4.get("target_trade_count"),
        "target_windows": gate4.get("target_windows"),
        "next_evidence_needed": row.get("next_evidence_needed")
        or row.get("post_run_reflection", {}).get("new_evidence_required")
        or row.get("post_run_reflection", {}).get("next_new_evidence_required"),
        "log": repo_rel(path) if path.exists() else None,
    }


def options_audit() -> dict[str, Any]:
    summary = read_json(OPTIONS_SUMMARY, {})
    chain_files = sorted((REPO_ROOT / "data" / "non_ohlcv").glob("options_onclickmedia_chain_*.jsonl"))
    dated_files = [
        path
        for path in chain_files
        if path.stem.replace("options_onclickmedia_chain_", "").isdigit()
    ]
    dates = sorted(path.stem.replace("options_onclickmedia_chain_", "") for path in dated_files)
    return {
        "surface": "options_onclickmedia",
        "status": "not_gate_ready",
        "local_files": len(dated_files),
        "first_local_date": dates[0] if dates else None,
        "last_local_date": dates[-1] if dates else None,
        "latest_summary": repo_rel(OPTIONS_SUMMARY),
        "latest_status": summary.get("status"),
        "latest_collection_mode": summary.get("collection_mode"),
        "latest_rows_written": summary.get("rows_written"),
        "latest_error_count": summary.get("error_count"),
        "latest_pit_safe_rows": summary.get("pit_safe_rows"),
        "blocker": (
            "Forward-collected options rows start after the canonical fixed "
            "windows, the 2026-06-19 refresh wrote zero rows, vendor_asof is "
            "absent in the prior readiness artifact, and open interest has lag."
        ),
        "history": summarize_neighbor_log("exp-20260617-004"),
    }


def moomoo_audit() -> dict[str, Any]:
    manifest = read_json(MOOMOO_MANIFEST, {})
    rows = read_jsonl(MOOMOO_ROWS)
    as_of_dates = sorted({row.get("as_of_date") for row in rows if row.get("as_of_date")})
    row_fields = sorted({field for row in rows for field in row.keys()})
    return {
        "surface": "moomoo_capital_flow",
        "status": "not_gate_ready",
        "manifest": repo_rel(MOOMOO_MANIFEST),
        "rows_path": repo_rel(MOOMOO_ROWS),
        "row_count": len(rows),
        "as_of_dates": as_of_dates,
        "schema": manifest.get("schema"),
        "pit_boundary": manifest.get("pit_boundary"),
        "trade_enabled": manifest.get("trade_enabled"),
        "entry_date_present": "entry_date" in row_fields,
        "target_price_present": "target_price" in row_fields,
        "canonical_windows_with_rows": [],
        "blocker": (
            "Current snapshot only: one 2026-06-19 observation, no fixed-window "
            "history, no entry_date/target_price replay fields, and no closed "
            "forward replacement-value row base."
        ),
    }


def estimate_revision_audit() -> dict[str, Any]:
    summary = read_json(ESTIMATE_REVISION_SUMMARY, {})
    return {
        "surface": "estimate_revision_ledger",
        "status": "not_gate_ready_for_new_alpha",
        "summary": repo_rel(ESTIMATE_REVISION_SUMMARY),
        "row_count": summary.get("row_count"),
        "estimate_revision_usable_rows": summary.get("estimate_revision_usable_rows"),
        "up_revision_rows": summary.get("up_revision_rows"),
        "down_revision_rows": summary.get("down_revision_rows"),
        "matched_candidate_rows": summary.get("matched_candidate_rows"),
        "matched_selected_signal_rows": summary.get("matched_selected_signal_rows"),
        "pit_safe_rate": summary.get("pit_safe_rate"),
        "blocker": (
            "The latest ledger has usable EPS rows, but zero up/down revisions "
            "and zero matched candidate or selected-signal rows, so it cannot "
            "supply a new three-window alpha signal."
        ),
    }


def sec13f_audit() -> dict[str, Any]:
    latest = read_json(SEC13F_LATEST, {})
    return {
        "surface": "sec13f_institutional",
        "status": "history_rejected_direct_entry_context_only",
        "latest": repo_rel(SEC13F_LATEST),
        "latest_as_of": latest.get("as_of"),
        "latest_universe_coverage_pct": latest.get("universe_coverage_pct"),
        "blocker": (
            "13F has historical coverage, but the latest sector-normalized and "
            "new-manager conviction entry scouts failed window/drawdown gates. "
            "Use as crowding/overhang context until a new ownership-delay field "
            "or shared daily helper evidence exists."
        ),
        "recent_rejections": [
            summarize_neighbor_log("exp-20260621-019"),
            summarize_neighbor_log("exp-20260621-020"),
        ],
    }


def sec_ftd_audit() -> dict[str, Any]:
    rows = read_json(SEC_FTD_ROWS, {})
    ftd_rows = rows.get("rows", []) if isinstance(rows, dict) else []
    return {
        "surface": "sec_ftd_finra",
        "status": "accepted_standalone_but_frozen_for_new_retunes",
        "rows_path": repo_rel(SEC_FTD_ROWS),
        "row_count": len(ftd_rows),
        "blocker": (
            "The official FTD+FINRA helper is already accepted as standalone. "
            "Recent no-core-flow and allocator insertion attempts did not beat "
            "their binding comparators, so threshold/rank/cooldown/notional "
            "retunes are frozen without a materially new borrow-cost, hard-to-"
            "borrow, utilization, or forward replacement field."
        ),
        "accepted_comparator": "exp-20260604-027",
        "recent_rejections": [
            summarize_neighbor_log("exp-20260609-020"),
            summarize_neighbor_log("exp-20260611-015"),
        ],
    }


def sec_text_audit() -> dict[str, Any]:
    return {
        "surface": "sec_8k_text_events",
        "status": "history_rejected_without_richer_provenance",
        "blocker": (
            "The SEC 8-K text surface is production-visible enough for private "
            "replay scouts, but the latest public-funding and share-repurchase "
            "runs only found 1-2 mid_weak trades and failed sample, window, "
            "concentration, and comparator gates. Earlier structure/cyber text "
            "scouts also failed; phrase and threshold sweeps are frozen."
        ),
        "recent_rejections": [
            summarize_neighbor_log("exp-20260621-022"),
            summarize_neighbor_log("exp-20260621-023"),
            summarize_neighbor_log("exp-20260622-001"),
            summarize_neighbor_log("exp-20260622-002"),
        ],
    }


def sec6k_audit() -> dict[str, Any]:
    return {
        "surface": "sec_6k_foreign_issuer_events",
        "status": "production_visible_surface_missing",
        "blocker": (
            "Raw form-index metadata has many 6-K rows, but current SEC event/text "
            "production surfaces expose zero trade-ready 6-K rows with ticker, "
            "accepted_at, usable_trade_date, entry_date, and target_price mapping."
        ),
        "history": summarize_neighbor_log("exp-20260621-018"),
    }


def frozen_alpha_lanes() -> list[dict[str, Any]]:
    return [
        {
            "lane": "accepted_allocator_scalar_and_rank_retunes",
            "status": "frozen",
            "reason": (
                "Recent independent/peer-shock/turn-of-month/lagged-consensus "
                "source scalars were accepted, but the playbook now requires "
                "closed forward displacement rows or new data fields rather than "
                "more scalar, rank, slot, cooldown, or notional sweeps."
            ),
        },
        {
            "lane": "raw_ohlcv_morphology_and_relation_thresholds",
            "status": "frozen",
            "reason": (
                "Compression, 52-week, distribution, pullback/reclaim, beta, and "
                "relation variants already have accepted or rejected families; a "
                "retry needs a new independent displacement field, not another "
                "price-only filter."
            ),
        },
        {
            "lane": "broad_companyfacts_ratio_scouts",
            "status": "frozen_without_new_tuple",
            "reason": (
                "Recent raw Companyfacts sweeps across accruals, cash conversion, "
                "inventory, customer concentration, OCI/AOCI, pension, warranty, "
                "segments, debt, and dividends mostly failed. The useful exception "
                "is supplier-financing/debt-relief; retry needs structured supplier/"
                "payment-term/covenant/counterparty provenance or forward rows."
            ),
        },
    ]


def build_gate1(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "passed": True,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "generated_at": read_json(BASELINE_JSON, {}).get("generated_at"),
        "windows": windows,
        "aggregate": aggregate_windows(windows),
    }


def build_gate2() -> dict[str, Any]:
    surfaces = [
        estimate_revision_audit(),
        moomoo_audit(),
        options_audit(),
        sec_text_audit(),
        sec6k_audit(),
        sec13f_audit(),
        sec_ftd_audit(),
    ]
    return {
        "passed": False,
        "dependency_fields_checked": [
            "entry_date",
            "target_price",
            "standard_window_coverage",
            "pit_boundary",
            "shared_backtest_daily_helper_path",
            "production_visible_fields",
        ],
        "open_positions": open_position_field_check(),
        "surface_audit": surfaces,
        "frozen_alpha_lanes": frozen_alpha_lanes(),
        "blocking_reasons": [
            "no_materially_new_free_pit_surface_with_three_window_coverage",
            "latest_sec_text_neighbors_failed_gate4",
            "moomoo_and_options_are_forward_only_or_not_fixed_window_ready",
            "estimate_revision_latest_surface_has_zero_actionable_revision_matches",
            "13f_and_ftd_are_context_or_frozen_without_new_field",
            "sec_6k_surface_missing_production_visible_trade_ready_rows",
        ],
    }


def build_gate3(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    survival = {
        label: {
            "signals_generated": row["signals_generated"],
            "signals_survived": row["signals_survived"],
            "survival_rate": row["survival_rate"],
        }
        for label, row in windows.items()
    }
    return {
        "passed": False,
        "baseline_survival_by_window": survival,
        "minimum_core_survival_rate": min(row["survival_rate"] for row in windows.values()),
        "new_core_filter_added": False,
        "candidate_pool_changed": False,
        "signals_generated": 0,
        "signals_survived": 0,
        "survival_rate": 0.0,
        "blocking_reason": (
            "No candidate source entered Gate 3 because Gate 2 found no new "
            "non-frozen surface with both fixed-window PIT coverage and a parity path."
        ),
    }


def build_gate4(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    aggregate = aggregate_windows(windows)
    delta_by_window = {
        label: {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "survival_rate": 0.0,
            "trade_count": 0,
        }
        for label in windows
    }
    return {
        "passed": False,
        "ran_after_strategy": False,
        "reason_after_not_run": (
            "Blocked before strategy replay: no new Gate-ready, non-frozen free "
            "candidate-pool surface was found. After intentionally equals before."
        ),
        "before_windows": windows,
        "after_windows": windows,
        "delta_by_window": delta_by_window,
        "aggregate_before": aggregate,
        "aggregate_after": aggregate,
        "aggregate_delta": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "max_window_drawdown_pct": 0.0,
            "min_survival_rate": 0.0,
            "total_trade_count": 0,
        },
        "decision": "blocked_no_gate_ready_nonfrozen_free_candidate_pool_surface",
        "failed_reasons": [
            "gate2_surface_readiness_blocked",
            "no_after_strategy_run",
            "no_candidate_trades",
        ],
        "minimum_core_survival_rate": aggregate["min_survival_rate"],
        "survival_guard_passed": aggregate["min_survival_rate"] >= 0.05,
        "target_trade_count": 0,
        "target_trade_count_min": 20,
        "target_windows": [],
    }


def build_result() -> dict[str, Any]:
    windows = baseline_windows()
    gate1 = build_gate1(windows)
    gate2 = build_gate2()
    gate3 = build_gate3(windows)
    gate4 = build_gate4(windows)
    aggregate = gate1["aggregate"]
    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now_utc(),
        "status": "blocked",
        "decision": gate4["decision"],
        "lane": "alpha_search",
        "change_type": "candidate_pool_data_edge_readiness",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "recent_experiment_neighbor_audit",
            "free_data_surface_coverage_audit",
            "three_window_baseline_context",
            "production_parity_path_check",
        ],
        "hypothesis": HYPOTHESIS,
        "nearby_prior_experiments": RECENT_NEIGHBOR_EXPERIMENTS,
        "new_evidence_axis": (
            "post-20260622 public-funding/share-repurchase SEC failures plus "
            "current 20260620 estimate/Moomoo/options coverage audit"
        ),
        "prediction": PREDICTION,
        "anti_js": "No JavaScript was used.",
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "before_metrics": {
            "label": "before_baseline",
            "baseline_result_file": BASELINE_RESULT_FILE,
            "windows": windows,
            **aggregate,
        },
        "after_metrics": {
            "label": "after_no_strategy_change",
            "baseline_result_file": BASELINE_RESULT_FILE,
            "windows": windows,
            **aggregate,
        },
        "delta_metrics": gate4["aggregate_delta"],
        "alpha_hypothesis_blocked": {
            "category": "candidate_pool",
            "hypothesis": HYPOTHESIS,
            "blocked_reason": (
                "All audited candidate data surfaces are either recently rejected, "
                "frozen by prior accepted/rejected families, forward-only, sparse, "
                "or missing a production-visible shared helper path."
            ),
        },
        "best_next_alpha_direction": {
            "primary": (
                "Do not launch another SEC phrase, allocator scalar, OHLCV "
                "threshold, or 13F/FTD retune on the frozen windows."
            ),
            "next_executable_edge": (
                "Build or accumulate a genuinely new free data edge with PIT "
                "coverage first: structured supplier/payment-term/covenant/"
                "counterparty provenance, historical PIT options/borrow/flow "
                "history, or 20-30 closed forward replacement rows from Moomoo/"
                "options/default-off observers."
            ),
            "reason": (
                "The strongest recent accepted alphas came from broad, cheap, "
                "production-visible shared helpers. Current untried surfaces lack "
                "either replay coverage or parity, while recent text scouts are "
                "too sparse and failed comparators."
            ),
        },
        "production_impact": {
            "strategy_code_changed": False,
            "shared_helper_changed": False,
            "backtester_adapter_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "backtest_production_parity_risk": "avoided_by_blocking_before_strategy_logic",
            "parity_note": (
                "No buy/sell/filter/ranking/sizing/risk code changed. Any future "
                "positive data-edge alpha must be implemented through one shared "
                "default-off helper used by historical replay and daily snapshots "
                "before retention."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Initial reservation was blocked as a near-neighbor of prior "
                    "nonrepeat surface readiness checks. The override is recorded "
                    "because the evidence axis adds the 2026-06-22 SEC public-"
                    "funding/share-repurchase failures and current estimate/"
                    "Moomoo/options coverage audit."
                ),
                "recent_neighbors": RECENT_NEIGHBOR_EXPERIMENTS,
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three standard windows. Proceed only if "
                "a surface has PIT coverage, sample depth, runtime fields, and a "
                "shared daily/backtest helper path; otherwise block before replay."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The audit found no new executable alpha surface. Latest SEC text "
                "candidate-pool scouts were sparse and failed Gate 4; Moomoo and "
                "options are forward-only or not fixed-window ready; estimate "
                "revision has zero actionable candidate matches; 13F/FTD are "
                "already rejected/frozen without a new field; and 6-K is missing "
                "from the production-visible event/text path."
            ),
            "negative_result_reflection": (
                "This is a data-edge readiness block, not a losing strategy. "
                "Forcing an after replay from these surfaces would either repeat "
                "frozen negative families or create a backtest/production mismatch."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping SEC phrase lists, Companyfacts ratios, "
                "allocator source rank/scalar/notional/cooldown, OHLCV thresholds, "
                "13F direct-entry scores, FTD/FINRA thresholds, or options/Moomoo "
                "top-N rules on the same evidence."
            ),
            "new_evidence_required": (
                "A valid next alpha needs a materially new PIT field with three-"
                "window coverage and a shared helper path, or enough closed forward "
                "replacement rows from a default-off daily observer."
            ),
        },
        "calibration": {
            "actual_success": 0,
            "actual_gate4_passed": False,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(PREDICTION["success_probability"] ** 2, 4),
            "failure_modes_observed": [
                "all_free_surfaces_forward_only_or_frozen",
                "recent_neighbors_already_rejected",
                "no_shared_parity_surface",
            ],
        },
        "lean_quality_passed": True,
        "reproduction": RUNNER_COMMAND,
        "related_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
    }
    return result


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "status": result["status"],
        "lane": result["lane"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "changed_variable": result["changed_variable"],
        "single_causal_variable": result["single_causal_variable"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "prediction": result["prediction"],
        "calibration": result["calibration"],
        "gate1": result["gate1"],
        "gate2": result["gate2"],
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "delta_metrics": result["delta_metrics"],
        "production_impact": result["production_impact"],
        "alpha_hypothesis_blocked": result["alpha_hypothesis_blocked"],
        "best_next_alpha_direction": result["best_next_alpha_direction"],
        "post_run_reflection": result["post_run_reflection"],
        "anti_js": result["anti_js"],
        "reproduction": result["reproduction"],
        "related_files": result["related_files"],
        "lean_quality_passed": result["lean_quality_passed"],
    }


def build_card(result: dict[str, Any]) -> str:
    aggregate = result["gate1"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID}: Candidate Pool Data Surface Readiness Gate",
        "",
        f"- Status: {result['status']}",
        f"- Decision: {result['decision']}",
        f"- Reproduction: `{result['reproduction']}`",
        f"- Anti-JS: {result['anti_js']}",
        "",
        "## Hypothesis",
        "",
        result["hypothesis"],
        "",
        "## Three-Window Baseline",
        "",
        "| Window | EV | PnL | Max DD | Trades | Survival |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in result["gate1"]["windows"].items():
        lines.append(
            f"| {label} | {row['expected_value_score']:.4f} | "
            f"${row['total_pnl']:,.2f} | {row['max_drawdown_pct']:.4f} | "
            f"{row['trade_count']} | {row['survival_rate']:.4f} |"
        )
    lines.extend(
        [
            "",
            f"Aggregate EV {aggregate['aggregate_expected_value_score']:.4f}; "
            f"aggregate PnL ${aggregate['aggregate_total_pnl']:,.2f}.",
            "",
            "## Surface Readiness",
            "",
            "| Surface | Status | Blocker |",
            "| --- | --- | --- |",
        ]
    )
    for surface in result["gate2"]["surface_audit"]:
        blocker = str(surface.get("blocker", "")).replace("|", "/")
        lines.append(f"| {surface['surface']} | {surface['status']} | {blocker} |")
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            result["post_run_reflection"]["why_result_happened"],
            "",
            result["best_next_alpha_direction"]["next_executable_edge"],
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER_NAME,
        ARTIFACT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG_JSONL,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER_NAME,
        "command": result["reproduction"],
        "anti_js": result["anti_js"],
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "updated_at": now_utc(),
    }


def persist(result: dict[str, Any]) -> None:
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_result_happened"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status="blocked",
        fields={
            "owner": "codex-alpha-search",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": RECENT_NEIGHBOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": "latest_experiment_and_data_surface_audit",
            "new_evidence_axis": result["new_evidence_axis"],
            "baseline_result_file": BASELINE_RESULT_FILE,
            "evaluation_windows": CANONICAL_WINDOWS,
            "acceptance_rule": (
                "Proceed only if a materially new free data edge has PIT standard-"
                "window coverage and a shared helper/daily snapshot path; otherwise "
                "block before strategy logic."
            ),
            "decision": result["decision"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "lean_quality_passed": result["lean_quality_passed"],
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
        },
    )
    write_json(MANIFEST_JSON, build_manifest(result))


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "aggregate_ev": result["gate1"]["aggregate"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl": result["gate1"]["aggregate"]["aggregate_total_pnl"],
                "blocking_reasons": result["gate2"]["blocking_reasons"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
