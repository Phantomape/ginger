"""exp-20260618-005: post SEC-item non-repeat alpha surface readiness.

Alpha-search direction-selection experiment. The single decision hypothesis is
that, after the June 18 SEC item-code failures, the best remaining alpha would
need a materially new PIT crowding/provenance field. The strongest near-term
lead is accounts-payable DPO extension: it improved all three fixed windows but
failed the drawdown guard. A credible retry would need a different PIT field
that explains that drawdown, not another DPO threshold, notional, hold, or
cooldown sweep.

This runner proves the blocker before any strategy code is changed. It writes
no production strategy code and changes no live/default order, ranking, sizing,
exit, LLM/news, watchlist, or daily-run behavior.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260618-005"
SLUG = "post_sec_item_nonrepeat_alpha_surface"
RUNNER_NAME = "quant/experiments/exp_20260618_005_post_sec_item_nonrepeat_alpha_surface.py"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260618_005_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
SEC13F_DIR = REPO_ROOT / "data" / "non_ohlcv" / "sec13f_institutional"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
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
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

CANONICAL_AGGREGATE = {
    "expected_value_score": 7.8941,
    "total_pnl": 234850.99,
    "trade_count": 61,
    "signals_generated": 164,
    "signals_survived": 135,
    "survival_rate": round(135 / 164, 4),
    "min_survival_rate": 0.7925,
    "max_drawdown_pct": 0.1119,
}

NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260617-010",
    "exp-20260617-020",
    "exp-20260617-021",
    "exp-20260618-001",
    "exp-20260618-002",
    "exp-20260618-003",
    "exp-20260618-004",
]

DPO_CONTEXT_IDS = [
    "exp-20260617-001",
    "exp-20260616-029",
    "exp-20260617-005",
    "exp-20260617-006",
    "exp-20260617-007",
]

SEC_ITEM_IDS = [
    "exp-20260617-020",
    "exp-20260617-022",
    "exp-20260617-023",
    "exp-20260617-024",
    "exp-20260617-025",
    "exp-20260617-027",
    "exp-20260618-001",
    "exp-20260618-002",
    "exp-20260618-003",
    "exp-20260618-004",
]

FINRA_FTD_IDS = [
    "exp-20260613-029",
    "exp-20260616-024",
    "exp-20260616-026",
    "exp-20260616-028",
]

PREDICTION = {
    "success_probability": 0.10,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "missing_historical_13f_crowding_context",
        "finra_closed_without_borrow_fee",
        "companyfacts_relief_fields_frozen",
        "sec_item_text_sparse_or_rejected",
        "options_forward_only",
    ],
    "confidence_reason": (
        "Recent positive leads either already promoted or failed drawdown/window "
        "gates; the only plausible non-repeat rescue is a new PIT crowding or "
        "provenance field, but local scans show that field is not available "
        "across the fixed windows."
    ),
    "recorded_at": "2026-06-18T04:13:10+00:00",
}

HYPOTHESIS = (
    "candidate_pool/data-edge: after the June 18 SEC-item failures, the best "
    "remaining alpha hypothesis is a materially new PIT crowding/provenance "
    "field that could explain the DPO drawdown-positive lead or supply a "
    "non-repeat candidate source; if historical PIT coverage for that field is "
    "absent and adjacent sources are frozen, another replay would be "
    "untrustworthy."
)

PRODUCTION_IMPACT = {
    "adapter_status": "analysis_only_no_strategy_or_adapter_change",
    "alters_candidate_ranking": False,
    "alters_exits": False,
    "alters_orders": False,
    "alters_signal_generation": False,
    "alters_sizing": False,
    "backtester_adapter_changed": False,
    "daily_snapshot_exposed": False,
    "live_ready": False,
    "live_realism_evaluated": False,
    "parity_note": (
        "No strategy, helper, runner, ranking, sizing, exit, watchlist, LLM/news, "
        "or order path changed. Any future positive alpha from these directions "
        "must use one shared default-off helper across historical replay and "
        "daily production observation before retention."
    ),
    "parity_test_added": False,
    "production_orders_changed": False,
    "production_signal_path_changed": False,
    "production_watchlist_changed": False,
    "replay_only": True,
    "run_adapter_changed": False,
    "shared_policy_changed": False,
    "trade_enabled": False,
    "uses_llm": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing_ids.add(json.loads(line).get("experiment_id"))
            except json.JSONDecodeError:
                continue
    if row.get("experiment_id") in existing_ids:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return completed.stdout.strip()


def _date_value(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def baseline_metrics(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "source": "docs/backtesting.md",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "expected_value_score": CANONICAL_AGGREGATE["expected_value_score"],
        "total_pnl": CANONICAL_AGGREGATE["total_pnl"],
        "total_trades": CANONICAL_AGGREGATE["trade_count"],
        "signals_generated": CANONICAL_AGGREGATE["signals_generated"],
        "signals_survived": CANONICAL_AGGREGATE["signals_survived"],
        "survival_rate": CANONICAL_AGGREGATE["survival_rate"],
        "max_drawdown_pct": CANONICAL_AGGREGATE["max_drawdown_pct"],
        "windows": CANONICAL_WINDOWS,
        "production_impact": {
            "scope": "analysis_only_no_strategy_change",
            "alters_candidate_ranking": False,
            "alters_exits": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "shared_policy_changed": False,
        },
    }


def gate4_no_change(failed_reasons: list[str]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    for label, metrics in CANONICAL_WINDOWS.items():
        by_window[label] = {
            "before_expected_value_score": metrics["expected_value_score"],
            "after_expected_value_score": metrics["expected_value_score"],
            "delta_expected_value_score": 0.0,
            "before_total_pnl": metrics["total_pnl"],
            "after_total_pnl": metrics["total_pnl"],
            "delta_total_pnl": 0.0,
            "before_trade_count": metrics["trade_count"],
            "after_trade_count": metrics["trade_count"],
            "delta_trade_count": 0,
            "before_max_drawdown_pct": metrics["max_drawdown_pct"],
            "after_max_drawdown_pct": metrics["max_drawdown_pct"],
            "delta_max_drawdown_pct": 0.0,
            "before_survival_rate": metrics["survival_rate"],
            "after_survival_rate": metrics["survival_rate"],
            "delta_survival_rate": 0.0,
        }
    return {
        "passed": False,
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_surface_after_sec_item_failures",
        "not_run_reason": "no_trustworthy_nonrepeat_strategy_change_after_readiness_blocker",
        "failed_reasons": failed_reasons,
        "aggregate_expected_value_delta": 0.0,
        "aggregate_total_pnl_delta": 0.0,
        "by_window": by_window,
        "minimum_core_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
        "survival_guard_passed": True,
        "target_trade_count": 0,
        "target_trade_count_min": 20,
        "target_windows": [],
    }


def find_jsonl_experiment(experiment_id: str) -> dict[str, Any] | None:
    if not EXPERIMENT_LOG_JSONL.exists():
        return None
    for line in EXPERIMENT_LOG_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("experiment_id") == experiment_id:
            return row
    return None


def load_experiment(experiment_id: str) -> dict[str, Any] | None:
    log_path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
    row = read_json(log_path)
    if row:
        return row
    return find_jsonl_experiment(experiment_id)


def summarize_experiment(experiment_id: str) -> dict[str, Any]:
    row = load_experiment(experiment_id) or {}
    gate = row.get("gate4") or {}
    delta = row.get("delta_metrics") or {}
    reflection = row.get("post_run_reflection") or {}
    return {
        "found": bool(row),
        "experiment_id": experiment_id,
        "decision": row.get("decision"),
        "status": row.get("status"),
        "aggregate_expected_value_delta": (
            gate.get("aggregate_ev_delta")
            if gate.get("aggregate_ev_delta") is not None
            else gate.get("aggregate_expected_value_delta")
            if gate.get("aggregate_expected_value_delta") is not None
            else delta.get("aggregate_expected_value_score")
            if delta.get("aggregate_expected_value_score") is not None
            else row.get("aggregate_expected_value_delta")
        ),
        "aggregate_pnl_delta": (
            gate.get("aggregate_pnl_delta")
            if gate.get("aggregate_pnl_delta") is not None
            else gate.get("aggregate_total_pnl_delta")
            if gate.get("aggregate_total_pnl_delta") is not None
            else delta.get("aggregate_total_pnl")
            if delta.get("aggregate_total_pnl") is not None
            else row.get("aggregate_strategy_total_pnl_delta")
            if row.get("aggregate_strategy_total_pnl_delta") is not None
            else row.get("total_pnl_delta")
        ),
        "failed_reasons": gate.get("failed_reasons") or [],
        "max_drawdown_worse": gate.get("max_drawdown_worse"),
        "target_trade_count": gate.get("target_trade_count"),
        "target_windows": gate.get("target_windows") or [],
        "windows_ev_regressed": gate.get("windows_ev_regressed"),
        "windows_pnl_regressed": gate.get("windows_pnl_regressed"),
        "forbidden_near_neighbor_retry": reflection.get("forbidden_near_neighbor_retry"),
        "new_evidence_required": reflection.get("new_evidence_required"),
        "why_result_happened": reflection.get("why_result_happened"),
        "log": f"experiments/logs/{experiment_id}.json",
    }


def audit_13f_surface() -> dict[str, Any]:
    latest = read_json(SEC13F_DIR / "latest.json", {})
    holdings_path_raw = latest.get("holdings_path")
    holdings_path = Path(holdings_path_raw) if holdings_path_raw else None
    if holdings_path and not holdings_path.is_absolute():
        holdings_path = REPO_ROOT / holdings_path
    holdings_payload = read_json(holdings_path, {}) if holdings_path else {}
    holdings = holdings_payload.get("holdings") or []
    report_period_counts = Counter(str(row.get("report_period")) for row in holdings[:5000])
    as_of = latest.get("as_of")
    as_of_date = _date_value(as_of)
    rows_by_window = {}
    for label, window in CANONICAL_WINDOWS.items():
        end = _date_value(window["end"])
        rows_by_window[label] = 0
        if as_of_date and end and as_of_date <= end:
            rows_by_window[label] = len(holdings)
    return {
        "source": "data/non_ohlcv/sec13f_institutional",
        "latest_path": repo_rel(SEC13F_DIR / "latest.json")
        if (SEC13F_DIR / "latest.json").exists()
        else None,
        "holdings_path": repo_rel(holdings_path) if holdings_path and holdings_path.exists() else None,
        "status": latest.get("status"),
        "as_of": as_of,
        "window_label": latest.get("window_label"),
        "universe_size": latest.get("universe_size"),
        "universe_covered_count": latest.get("universe_covered_count"),
        "universe_coverage_pct": latest.get("universe_coverage_pct"),
        "holdings_count": len(holdings),
        "sample_fields": sorted(holdings[0].keys()) if holdings else [],
        "sample_report_period_counts": dict(report_period_counts.most_common(5)),
        "historical_pit_rows_by_window": rows_by_window,
        "coverage_conclusion": (
            "The local 13F institutional file is a single latest snapshot "
            "generated after all canonical windows. It cannot be used as a PIT "
            "crowding context for 2024-10-02 -> 2026-04-21 Gate 4 replay."
        ),
    }


def audit_options_surface() -> dict[str, Any]:
    option_log = summarize_experiment("exp-20260617-004")
    row = load_experiment("exp-20260617-004") or {}
    audit = row.get("options_coverage_audit") or {}
    return {
        "history": option_log,
        "chain_file_count": audit.get("chain_file_count"),
        "first_chain_date": audit.get("first_chain_date"),
        "last_chain_date": audit.get("last_chain_date"),
        "chain_files_by_fixed_window": audit.get("chain_files_by_fixed_window"),
        "rows_with_vendor_asof": audit.get("rows_with_vendor_asof"),
        "coverage_conclusion": audit.get("coverage_conclusion"),
    }


def audit_finra_ftd_surface() -> dict[str, Any]:
    finra_rows = read_json(NON_OHLCV_DIR / "finra_short_interest" / "rows.json", {})
    ftd_rows = read_json(NON_OHLCV_DIR / "sec_ftd" / "rows.json", {})
    return {
        "finra_row_count": len(finra_rows.get("rows") or []),
        "finra_updated_at": finra_rows.get("updated_at"),
        "ftd_row_count": len(ftd_rows.get("rows") or []),
        "ftd_updated_at": ftd_rows.get("updated_at"),
        "history": {eid: summarize_experiment(eid) for eid in FINRA_FTD_IDS},
        "coverage_conclusion": (
            "FINRA/FTD coverage exists, but the line is closed for share-count "
            "directional entry after broad and core failures. A valid reopen "
            "needs PIT borrow fee, hard-to-borrow, utilization, or availability, "
            "not another days-to-cover/short-change/FTD threshold."
        ),
    }


def build_candidate_decisions() -> list[dict[str, Any]]:
    dpo = summarize_experiment("exp-20260617-001")
    return [
        {
            "candidate": "dpo_extension_with_pit_crowding_context",
            "decision": "blocked_missing_historical_13f_crowding_context",
            "evidence": {
                "dpo_lead": dpo,
                "sec13f_surface": audit_13f_surface(),
            },
            "why_not_run": (
                "DPO extension is the strongest near-term lead because all three "
                "windows improved, but it failed drawdown drift. The only non-repeat "
                "rescue checked here, PIT ownership/crowding context, lacks historical "
                "fixed-window coverage locally. A DPO threshold/notional/hold/cooldown "
                "retry is explicitly frozen."
            ),
        },
        {
            "candidate": "fresh_sec_item_or_text_semantics",
            "decision": "blocked_recent_item_semantics_rejected_or_sparse",
            "evidence": {eid: summarize_experiment(eid) for eid in SEC_ITEM_IDS},
            "why_not_run": (
                "Recent SEC item/text scouts for timeliness, offerings, S-8, NT late "
                "filing, proxy pressure, restructuring, combinations, contract "
                "termination, and vote results failed Gate 4 or had no sample. "
                "Another item-code or regex scout would repeat a frozen surface."
            ),
        },
        {
            "candidate": "finra_ftd_borrow_or_supply_surface",
            "decision": "blocked_closed_without_new_borrow_fee_availability_field",
            "evidence": audit_finra_ftd_surface(),
            "why_not_run": (
                "The data is present, but core and broad FINRA borrow-pressure plus "
                "covering-relief tests already failed. The playbook requires a true "
                "borrow-cost or availability field before reopening this line."
            ),
        },
        {
            "candidate": "options_chain_skew_or_flow",
            "decision": "blocked_forward_only_no_fixed_window_rows",
            "evidence": audit_options_surface(),
            "why_not_run": (
                "Options rows are forward-collected after the canonical windows and "
                "have no vendor_asof coverage for Gate 4. Using them now would create "
                "a backtest/production mismatch."
            ),
        },
        {
            "candidate": "raw_companyfacts_relief_overhang",
            "decision": "blocked_frozen_relief_neighbors_after_drawdown_window_failures",
            "evidence": {eid: summarize_experiment(eid) for eid in DPO_CONTEXT_IDS},
            "why_not_run": (
                "The recent Companyfacts relief/overhang family often looks positive "
                "in aggregate, but failed drawdown or old_thin/window gates. The next "
                "valid evidence must be a new PIT decomposition such as supplier "
                "concentration, contract terms, maturity cliffs, segment/customer "
                "capacity, or closed forward replacement rows."
            ),
        },
        {
            "candidate": "shared_default_off_adapter_promotion",
            "decision": "blocked_no_unpromoted_positive_lead",
            "evidence": {
                "sbc_shared": summarize_experiment("exp-20260616-015"),
                "sbc_allocator_extension": summarize_experiment("exp-20260616-016"),
            },
            "why_not_run": (
                "The highest-priority meta family remains shared default-off helpers, "
                "but the recent positive SBC lead has already been promoted. The next "
                "allocator/source extensions failed, so there is no unpromoted positive "
                "lead to move across the parity boundary today."
            ),
        },
        {
            "candidate": "static_intraindustry_liquidity_leader_lead_lag",
            "decision": "blocked_static_source_rejected_forward_regime_only",
            "evidence": {"lead_lag": summarize_experiment("exp-20260617-021")},
            "why_not_run": (
                "Static lead-lag was rejected and the playbook only sanctions a "
                "regime-conditioned forward/live-pilot path, not frozen-window "
                "threshold re-slicing."
            ),
        },
    ]


def build_result() -> dict[str, Any]:
    failed_reasons = [
        "missing_historical_13f_crowding_context",
        "dpo_context_rescue_not_gate4_ready_without_new_pit_field",
        "finra_short_interest_closed_no_borrow_fee_or_availability",
        "companyfacts_relief_overhang_neighbors_frozen",
        "sec_item_text_semantics_sparse_or_recently_rejected",
        "options_chain_forward_only_no_fixed_window_rows",
        "no_unpromoted_positive_lead_for_shared_adapter",
    ]
    gate4 = gate4_no_change(failed_reasons)
    candidates = build_candidate_decisions()
    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": "blocked",
        "decision": gate4["decision"],
        "lane": "alpha_search",
        "change_type": "nonrepeat_alpha_direction_blocker",
        "mechanism_family": "nonrepeat_alpha_direction_blocker",
        "trial_family": "post_sec_item_nonrepeat_alpha_surface_readiness",
        "trial_variant_id": "post_sec_item_nonrepeat_alpha_surface_readiness_v1",
        "changed_variable": "post_sec_item_nonrepeat_alpha_surface_readiness_v1",
        "single_causal_variable": "post_sec_item_nonrepeat_alpha_surface_readiness_v1",
        "causal_components": [
            "three_window_gate_blocker",
            "post_sec_item_history_check",
            "pit_data_coverage_audit",
            "production_parity_boundary",
            "no_strategy_change",
        ],
        "hypothesis": HYPOTHESIS,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260617-001": (
                    "DPO extension improved aggregate EV +1.2688 and PnL +$18,973.98 "
                    "with all three windows improved and 194 trades, but failed "
                    "drawdown drift +1.42pp; no DPO threshold/notional/hold retry."
                ),
                "exp-20260617-010": (
                    "Prior nonrepeat readiness blocked missing PIT revision, structured "
                    "contract, options, borrow, and unpromoted shared-adapter leads."
                ),
                "exp-20260618-001_to_004": (
                    "Fresh SEC item/text scouts were rejected or zero-sample after "
                    "three-window Gate 4."
                ),
                "finra_ftd_family": (
                    "Core and broad FINRA/FTD share-count surfaces failed or were "
                    "retired; valid reopen needs borrow fee/availability."
                ),
                "sec13f_institutional": (
                    "Local 13F file is a single latest 2026 snapshot, not historical "
                    "PIT coverage for the canonical windows."
                ),
            },
            "3_single_decision_hypothesis": "post_sec_item_nonrepeat_alpha_surface_readiness_v1",
            "4_acceptance_standard": (
                "Use docs/backtesting.md canonical three windows. A strategy launch "
                "requires aggregate EV/PnL improvement, no unacceptable window "
                "regression, survival >=5%, enough target trades, drawdown and "
                "concentration guards, accepted comparator checks, and a shared "
                "daily/backtest helper before retention. If no non-repeat PIT field "
                "exists, block with zero production impact."
            ),
            "5_reproducibility": f".venv\\Scripts\\python.exe -B {RUNNER_NAME}",
        },
        "prediction": PREDICTION,
        "calibration": {
            "actual_gate4_passed": False,
            "actual_success": 0,
            "brier_score": round((PREDICTION["success_probability"] - 0.0) ** 2, 4),
            "predicted_success_probability": PREDICTION["success_probability"],
            "failure_modes_observed": failed_reasons,
        },
        "before_metrics": baseline_metrics("before_baseline"),
        "after_metrics": baseline_metrics("after_no_strategy_change"),
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "aggregate_trade_count": 0,
            "minimum_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
        },
        "gate4": gate4,
        "candidate_decisions": candidates,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "The current strongest alpha lead is not absent; it is DPO extension, "
                "but it already failed the hard drawdown guard. The only credible "
                "non-repeat rescue checked here, PIT crowding/provenance context, is "
                "not available across the fixed windows: 13F is latest-only, FINRA/FTD "
                "requires a new borrow-cost/availability feed, options are forward-only, "
                "and SEC item/text plus raw Companyfacts relief neighbors are frozen "
                "or recently rejected. Launching another replay today would be a "
                "near-neighbor retune or a production/backtest mismatch."
            ),
            "negative_reflection": (
                "Forcing a fresh SEC item-code, DPO threshold, Companyfacts relief, "
                "FINRA share-count, options proxy, 13F latest-snapshot, or OHLCV "
                "relation replay would mostly optimize frozen windows without a "
                "new PIT decision variable."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry DPO extension, debt/D&A/CapEx/working-capital relief, "
                "SEC item-code/text, FINRA/FTD share-count, 13F latest-snapshot, "
                "options-chain, or static intraindustry lead-lag variants on frozen "
                "windows without a new PIT field or closed forward replacement-value "
                "rows."
            ),
            "new_evidence_required": (
                "Best next alpha work is data-edge construction, not another replay: "
                "historical PIT 13F/crowding snapshots by filing availability date, "
                "supplier/customer concentration or payment-term contract fields for "
                "DPO, borrow fee/availability/utilization, PIT options history with "
                "vendor_asof, or mature closed forward replacement-value rows from "
                "accepted shared helpers."
            ),
            "best_next_alpha_direction": (
                "Build one historical PIT crowding/provenance field that can explain "
                "DPO drawdown or collect enough closed forward replacement-value rows; "
                "then run shared-paper-first Gate 1-4. Until then, prefer no strategy "
                "change over a frozen-neighbor scout."
            ),
        },
        "baseline_result_file": BASELINE_RESULT_FILE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "anti_js": "No JavaScript was used.",
        "reproduction": f".venv\\Scripts\\python.exe -B {RUNNER_NAME}",
    }
    return result


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "status": result["status"],
        "decision": result["decision"],
        "lane": result["lane"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "single_causal_variable": result["single_causal_variable"],
        "hypothesis": result["hypothesis"],
        "pre_run_questions": result["pre_run_questions"],
        "prediction": result["prediction"],
        "calibration": result["calibration"],
        "aggregate_expected_value_delta": result["delta_metrics"][
            "aggregate_expected_value_score"
        ],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"][
            "aggregate_total_pnl"
        ],
        "gate4": result["gate4"],
        "candidate_decisions": result["candidate_decisions"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": result["anti_js"],
    }


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: post SEC-item non-repeat alpha surface readiness",
        "",
        f"- Decision: `{result['decision']}`",
        f"- Status: `{result['status']}`",
        "- Lane: `alpha_search`",
        "- Production impact: no strategy, order, ranking, sizing, exit, LLM/news, or watchlist change.",
        "",
        "## Hypothesis",
        "",
        result["hypothesis"],
        "",
        "## Gate 4",
        "",
        f"- Aggregate EV delta: `{result['gate4']['aggregate_expected_value_delta']:+.4f}`",
        f"- Aggregate PnL delta: `${result['gate4']['aggregate_total_pnl_delta']:+,.2f}`",
        f"- Failed reasons: `{', '.join(result['gate4']['failed_reasons'])}`",
        "",
        "| Window | EV Before | EV After | PnL Before | PnL After | Survival |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, window in result["gate4"]["by_window"].items():
        lines.append(
            "| {label} | {evb:.4f} | {eva:.4f} | ${pnb:,.2f} | ${pna:,.2f} | {surv:.2%} |".format(
                label=label,
                evb=window["before_expected_value_score"],
                eva=window["after_expected_value_score"],
                pnb=window["before_total_pnl"],
                pna=window["after_total_pnl"],
                surv=window["before_survival_rate"],
            )
        )
    lines.extend(["", "## Candidate Readiness", "", "| Candidate | Decision | Reason |", "|---|---|---|"])
    for item in result["candidate_decisions"]:
        lines.append(f"| `{item['candidate']}` | `{item['decision']}` | {item['why_not_run']} |")
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            result["post_run_reflection"]["why_result_happened"],
            "",
            "## Next Evidence",
            "",
            result["post_run_reflection"]["new_evidence_required"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def write_manifest(result: dict[str, Any]) -> None:
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
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "git_head": git_value("rev-parse", "HEAD"),
        "git_branch": git_value("branch", "--show-current"),
        "files": {repo_rel(path): sha256(path) for path in files},
        "command": result["reproduction"],
        "anti_js": "No JavaScript was used.",
    }
    write_json(MANIFEST_JSON, manifest)


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
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "causal_components": result["causal_components"],
        "prior_trial_count": 15,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "three_window_nonrepeat_data_edge_readiness_after_sec_item_failures",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "decision": result["decision"],
        "summary": result["post_run_reflection"]["why_result_happened"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": result["delta_metrics"][
            "aggregate_expected_value_score"
        ],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"][
            "aggregate_total_pnl"
        ],
        "post_run_reflection": result["post_run_reflection"],
        "production_impact": result["production_impact"],
        "gate4": result["gate4"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
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
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "failed_reasons": result["gate4"]["failed_reasons"],
                "best_next_alpha_direction": result["post_run_reflection"][
                    "best_next_alpha_direction"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
