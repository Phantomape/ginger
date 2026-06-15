from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260615-014"
SLUG = "nonrepeat_alpha_candidate_blocker"
RUNNER_NAME = "quant/experiments/exp_20260615_014_nonrepeat_alpha_candidate_blocker.py"

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
LOG_PATH = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_PATH = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
MANIFEST_PATH = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_PATH = ROOT / "docs" / "experiment_log.jsonl"


CANONICAL_BASELINE = {
    "source": "docs/backtesting.md",
    "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
    "aggregate": {
        "expected_value_score": 7.8941,
        "total_pnl": 234850.99,
        "trade_count": 61,
        "signals_generated": 164,
        "signals_survived": 135,
        "survival_rate": round(135 / 164, 4),
        "min_survival_rate": 0.7925,
        "max_drawdown_pct": 0.1119,
    },
    "by_window": {
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
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_value(*args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return proc.stdout.strip()


def count_jsonl(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    skipped = sum(1 for row in rows if row.get("skipped") or row.get("status") == "skipped")
    return {
        "source": path.relative_to(ROOT).as_posix(),
        "exists": path.exists(),
        "row_count": len(rows),
        "skipped_rows": skipped,
        "usable_rows": max(len(rows) - skipped, 0),
        "sample_keys": sorted(rows[0].keys())[:20] if rows else [],
    }


def experiment_log(eid: str, jsonl_rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_id = ROOT / "experiments" / "logs" / f"{eid}.json"
    obj = read_json(per_id, {})
    if obj:
        return obj
    for row in reversed(jsonl_rows):
        if row.get("experiment_id") == eid:
            return row
    return {}


def recent_history_summary(jsonl_rows: list[dict[str, Any]]) -> dict[str, Any]:
    recent = [
        row
        for row in jsonl_rows
        if str(row.get("experiment_id", "")) >= "exp-20260614-000"
    ]
    alpha_rows = [row for row in recent if row.get("lane") == "alpha_search" or row.get("change_type")]
    rejected = [
        row
        for row in alpha_rows
        if str(row.get("status") or row.get("decision") or "").startswith("rejected")
        or "rejected" in str(row.get("decision") or "")
    ]
    accepted = [
        row
        for row in alpha_rows
        if str(row.get("status") or row.get("decision") or "").startswith("accepted")
        or "accepted" in str(row.get("decision") or "")
    ]
    key_ids = [
        "exp-20260614-020",
        "exp-20260614-021",
        "exp-20260614-023",
        "exp-20260614-024",
        "exp-20260614-025",
        "exp-20260614-027",
        "exp-20260614-029",
        "exp-20260615-001",
        "exp-20260615-002",
        "exp-20260615-003",
        "exp-20260615-006",
        "exp-20260615-008",
        "exp-20260615-009",
        "exp-20260615-010",
        "exp-20260615-011",
        "exp-20260615-012",
        "exp-20260615-013",
    ]
    key_rows = []
    for eid in key_ids:
        obj = experiment_log(eid, jsonl_rows)
        key_rows.append(
            {
                "experiment_id": eid,
                "status": obj.get("status"),
                "decision": obj.get("decision") or (obj.get("result") or {}).get("decision"),
                "changed_variable": obj.get("changed_variable")
                or obj.get("single_causal_variable"),
                "delta_metrics": obj.get("delta_metrics")
                or (obj.get("result") or {}).get("delta_metrics"),
            }
        )
    return {
        "recent_rows_since_20260614": len(recent),
        "recent_alpha_like_rows": len(alpha_rows),
        "recent_rejected_or_rejected_decision_rows": len(rejected),
        "recent_accepted_or_accepted_decision_rows": len(accepted),
        "key_recent_experiments": key_rows,
    }


def coverage_snapshot() -> dict[str, Any]:
    estimate_summary = read_json(
        ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_summary_20260614.json",
        {},
    )
    options_summary = read_json(
        ROOT / "data" / "non_ohlcv" / "options_onclickmedia_summary_20260612.json",
        {},
    )
    form4_summary = read_json(
        ROOT / "data" / "non_ohlcv" / "form4_backfill_summary_20260614.json",
        {},
    )
    kova_snapshot = read_json(
        ROOT / "data" / "kova" / "snapshots" / "kova_data_snapshot_20260614.json",
        {},
    )
    return {
        "kova_fundamentals_companyfacts_growth_20260614": count_jsonl(
            ROOT / "data" / "kova" / "fundamentals" / "companyfacts_growth_20260614.jsonl"
        ),
        "kova_rs_proxy_20260614": count_jsonl(
            ROOT / "data" / "kova" / "rs_proxy" / "rs_proxy_20260614.jsonl"
        ),
        "kova_sec13f_ownership_20260614": count_jsonl(
            ROOT / "data" / "kova" / "institutional" / "sec13f_ownership_20260614.jsonl"
        ),
        "kova_intraday_ohlcv_20260614": count_jsonl(
            ROOT / "data" / "kova" / "intraday" / "intraday_ohlcv_20260614.jsonl"
        ),
        "estimate_revision_summary_20260614": {
            "source": "data/non_ohlcv/estimate_revision_ledger_summary_20260614.json",
            "row_count": estimate_summary.get("row_count"),
            "up_revision_rows": estimate_summary.get("up_revision_rows"),
            "down_revision_rows": estimate_summary.get("down_revision_rows"),
            "matched_candidate_rows": estimate_summary.get("matched_candidate_rows"),
            "candidate_match_rate": estimate_summary.get("candidate_match_rate"),
            "pit_safe_rate": estimate_summary.get("pit_safe_rate"),
        },
        "options_onclickmedia_summary_20260612": {
            "source": "data/non_ohlcv/options_onclickmedia_summary_20260612.json",
            "closed_outcome_rows": options_summary.get("closed_outcome_rows")
            or options_summary.get("closed_rows"),
            "rows_written": options_summary.get("rows_written"),
            "symbol_count": options_summary.get("symbol_count"),
            "decision_context": "exp-20260613-025 observed no closed outcome overlay strong enough for Gate 4.",
        },
        "form4_backfill_summary_20260614": {
            "source": "data/non_ohlcv/form4_backfill_summary_20260614.json",
            "rows_written": form4_summary.get("rows_written"),
            "open_market_purchase_count": form4_summary.get("open_market_purchase_count"),
            "transaction_code_counts": form4_summary.get("transaction_code_counts"),
            "tickers_mapped": form4_summary.get("tickers_mapped"),
        },
        "kova_snapshot_20260614": {
            "source": "data/kova/snapshots/kova_data_snapshot_20260614.json",
            "fundamentals_rows_written": (
                (kova_snapshot.get("surfaces") or {})
                .get("fundamentals_companyfacts_growth", {})
                .get("rows_written")
            ),
            "rs_proxy_rows_written": (
                (kova_snapshot.get("surfaces") or {})
                .get("rs_proxy", {})
                .get("rows_written")
            ),
            "intraday_status": (
                (kova_snapshot.get("surfaces") or {})
                .get("intraday_ohlcv", {})
                .get("status")
            ),
            "sec13f_status": (
                (kova_snapshot.get("surfaces") or {})
                .get("institutional_sec13f_ownership", {})
                .get("status")
            ),
        },
    }


def gate4_noop() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for label, row in CANONICAL_BASELINE["by_window"].items():
        rows[label] = {
            "before_expected_value_score": row["expected_value_score"],
            "after_expected_value_score": row["expected_value_score"],
            "delta_expected_value_score": 0.0,
            "before_total_pnl": row["total_pnl"],
            "after_total_pnl": row["total_pnl"],
            "delta_total_pnl": 0.0,
            "before_max_drawdown_pct": row["max_drawdown_pct"],
            "after_max_drawdown_pct": row["max_drawdown_pct"],
            "delta_max_drawdown_pct": 0.0,
            "before_trade_count": row["trade_count"],
            "after_trade_count": row["trade_count"],
            "delta_trade_count": 0,
            "before_survival_rate": row["survival_rate"],
            "after_survival_rate": row["survival_rate"],
            "delta_survival_rate": 0.0,
        }
    aggregate = CANONICAL_BASELINE["aggregate"]
    return {
        "applicable": False,
        "reason": "No strategy policy was launched because every reviewed alpha lane failed anti-repeat, coverage, PIT, or Gate 4 readiness checks.",
        "aggregate_before": aggregate,
        "aggregate_after": aggregate,
        "aggregate_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "max_drawdown_pct": 0.0,
            "survival_rate": 0.0,
        },
        "by_window": rows,
    }


def candidate_reviews(coverage: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "candidate": "sec_text_demand_or_cost_or_liquidity_evidence",
            "alpha_hypothesis": "Issuer text about demand, backlog, order strength, restructuring, deleveraging, or liquidity could identify underreaction when confirmed by price strength.",
            "history_check": [
                "exp-20260615-001",
                "exp-20260615-011",
                "exp-20260615-012",
                "exp-20260615-013",
                "exp-20260614-013",
                "exp-20260614-015",
            ],
            "current_evidence": {
                "sec_text_file": "data/non_ohlcv/sec_filing_text_20260614.jsonl",
                "sec_text_rows": count_jsonl(ROOT / "data" / "non_ohlcv" / "sec_filing_text_20260614.jsonl"),
            },
            "decision": "blocked_all_candidates_frozen",
            "why_not_run": "The latest SEC text lanes rejected both generic and quantified backlog/order evidence plus restructuring and deleveraging/liquidity variants; another keyword/evidence-span replay would be a frozen near-neighbor without new semantics.",
            "retry_requires": "A materially new PIT semantic field, such as customer/supplier identity or externally verifiable contract economics, wired through shared paper parity.",
        },
        {
            "candidate": "companyfacts_quality_growth_or_cash_conversion",
            "alpha_hypothesis": "PIT Companyfacts quality and growth should improve candidate selection by selecting firms with healthier economics than price-only leaders.",
            "history_check": [
                "exp-20260614-020",
                "exp-20260614-021",
                "exp-20260614-023",
                "exp-20260614-024",
                "exp-20260614-025",
                "exp-20260614-027",
                "exp-20260614-029",
                "exp-20260615-002",
                "exp-20260615-003",
                "exp-20260615-006",
                "exp-20260615-008",
                "exp-20260615-010",
            ],
            "current_evidence": coverage["kova_fundamentals_companyfacts_growth_20260614"],
            "decision": "blocked_near_neighbor_overfit_risk",
            "why_not_run": "Coverage exists, but the last two days already tested cash conversion, accruals, low asset growth, cash-backed low asset growth, industry-relative asset growth, FCF capex coverage, gross profitability, and share contraction with mostly rejected Gate 4 behavior or drawdown drift.",
            "retry_requires": "A new economic mechanism not expressible as another quality/growth threshold, or forward evidence that the positive accrual signal can be isolated without drawdown drift.",
        },
        {
            "candidate": "13f_or_form4_ownership_pressure",
            "alpha_hypothesis": "Institutional crowding relief, low sponsorship, or insider activity may create non-price candidate-pool edge.",
            "history_check": [
                "exp-20260615-009",
                "exp-20260613-014",
                "exp-20260613-026",
                "exp-20260612-015",
                "exp-20260612-016",
                "exp-20260612-023",
            ],
            "current_evidence": {
                "sec13f": coverage["kova_sec13f_ownership_20260614"],
                "form4": coverage["form4_backfill_summary_20260614"],
            },
            "decision": "blocked_data_surface_insufficient_and_recently_rejected",
            "why_not_run": "The current Kova 13F surface has skipped/empty rows, and the latest low-crowding 13F leadership scout was rejected; Form4/Form144 variants are already frozen without a new relation-quality discriminator.",
            "retry_requires": "Usable PIT 13F holdings with issuer mapping across all windows, or a new Form4 relation classifier with enough closed replay rows.",
        },
        {
            "candidate": "analyst_estimate_revision_or_pead_extension",
            "alpha_hypothesis": "Estimate revision breadth and post-earnings drift may catch expectation underreaction using a free non-price data edge.",
            "history_check": [
                "exp-20260611-005",
                "exp-20260610-025",
                "exp-20260614-005",
            ],
            "current_evidence": coverage["estimate_revision_summary_20260614"],
            "decision": "blocked_data_surface_insufficient",
            "why_not_run": "The current estimate summary has no matched candidate rows, so a three-window Gate 4 replay would be empty or dominated by stale/current-only observations.",
            "retry_requires": "PIT estimate revision breadth, dispersion, and matched candidate rows across the canonical windows.",
        },
        {
            "candidate": "options_or_intraday_free_data_edge",
            "alpha_hypothesis": "Options skew/open-interest or intraday behavior could expand candidates with a market-implied edge unavailable in daily OHLCV.",
            "history_check": [
                "exp-20260613-025",
                "exp-20260613-023",
            ],
            "current_evidence": {
                "options": coverage["options_onclickmedia_summary_20260612"],
                "intraday": coverage["kova_intraday_ohlcv_20260614"],
            },
            "decision": "blocked_no_closed_outcomes_or_api_backfill",
            "why_not_run": "Options work remains observed-only without enough closed outcomes, while current Kova intraday rows are skipped/empty and cannot support a PIT historical replay.",
            "retry_requires": "Closed options outcomes or free intraday backfill coverage for all canonical windows.",
        },
        {
            "candidate": "ohlcv_only_candidate_pool_or_allocator_retune",
            "alpha_hypothesis": "A cheaper price/volume relation could still improve entry ranking or candidate selection.",
            "history_check": [
                "exp-20260613-020",
                "exp-20260613-021",
                "exp-20260614-006",
                "exp-20260614-028",
                "exp-20260615-005",
            ],
            "current_evidence": coverage["kova_rs_proxy_20260614"],
            "decision": "blocked_all_candidates_frozen",
            "why_not_run": "The playbook freezes OHLCV relabels, state/ranking threshold sweeps, and allocator arbitration retunes unless there is new data; the current RS proxy snapshot is narrow and not a new production-visible data edge.",
            "retry_requires": "A non-price PIT source, not another ranking/scalar/threshold sweep over existing OHLCV rows.",
        },
        {
            "candidate": "accepted_default_off_adapter_maturation",
            "alpha_hypothesis": "Accepted default-off helpers may be promotable once forward replacement value closes cleanly.",
            "history_check": [
                "exp-20260611-022",
                "exp-20260612-019",
                "exp-20260614-003",
            ],
            "current_evidence": {
                "paper_sleeve_state": "daily forward rows exist, but this is activation evidence rather than a new three-window strategy change",
            },
            "decision": "blocked_not_a_new_gate4_alpha_optimization",
            "why_not_run": "This is the right monitoring lane, but it is observed-only until enough closed true-trigger rows exist; it should not be sold as a new historical alpha optimization.",
            "retry_requires": "At least 20 closed true-trigger rows for one sleeve with replacement value versus cash, SPY, and QQQ.",
        },
    ]


def build_backtest_snapshot(label: str) -> dict[str, Any]:
    aggregate = CANONICAL_BASELINE["aggregate"]
    return {
        "label": label,
        "expected_value_score": aggregate["expected_value_score"],
        "sharpe": None,
        "sharpe_daily": None,
        "benchmarks": {"strategy_total_return_pct": None},
        "max_drawdown_pct": aggregate["max_drawdown_pct"],
        "win_rate": None,
        "total_trades": aggregate["trade_count"],
        "signals_generated": aggregate["signals_generated"],
        "signals_survived": aggregate["signals_survived"],
        "survival_rate": aggregate["survival_rate"],
        "total_pnl": aggregate["total_pnl"],
        "windows": CANONICAL_BASELINE["by_window"],
    }


def build_result() -> dict[str, Any]:
    jsonl_rows = read_jsonl(EXPERIMENT_LOG_PATH)
    coverage = coverage_snapshot()
    reviews = candidate_reviews(coverage)
    gate4 = gate4_noop()
    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": "blocked",
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_candidate",
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": "After the latest June 15 history scan, at least one non-repeat production-visible free-data alpha direction may remain; launch only if coverage, PIT lineage, anti-repeat, and Gate 4 applicability checks pass.",
        "change_summary": "Alpha direction triage only; no strategy, ranking, sizing, exit, or production order logic changed.",
        "change_type": "alpha_direction_selection",
        "mechanism_family": "free_data_candidate_pool_prioritization",
        "trial_family": "alpha_direction_triage",
        "trial_variant_id": "blocker_scan_v1",
        "changed_variable": "highest_priority_nonrepeat_alpha_candidate_selection_after_20260615_history_scan_v1",
        "causal_components": [
            "history_scan",
            "data_surface_coverage_check",
            "anti_repeat_gate",
            "gate4_applicability_decision",
        ],
        "nearby_prior_experiments": [
            "exp-20260614-012",
            "exp-20260614-020",
            "exp-20260614-027",
            "exp-20260615-008",
            "exp-20260615-009",
            "exp-20260615-010",
            "exp-20260615-013",
        ],
        "gate1": {
            "baseline_source": "docs/backtesting.md",
            "baseline_result_file": CANONICAL_BASELINE["baseline_result_file"],
            "aggregate_baseline": CANONICAL_BASELINE["aggregate"],
            "by_window_baseline": CANONICAL_BASELINE["by_window"],
        },
        "gate2": {
            "no_strategy_rows_created": True,
            "entry_date_required_for_future_alpha": True,
            "target_price_required_for_future_alpha": True,
            "runtime_field_check": "Not applicable because no executable signal rows were created; future strategy launches must prove both fields exist before Gate 4.",
        },
        "gate3": {
            "filter_added": False,
            "baseline_min_survival_rate": CANONICAL_BASELINE["aggregate"]["min_survival_rate"],
            "survival_guard_passed_for_baseline": True,
        },
        "gate4": gate4,
        "before_metrics": build_backtest_snapshot("before_baseline"),
        "after_metrics": build_backtest_snapshot("after_no_strategy_change"),
        "delta_metrics": gate4["aggregate_delta"],
        "history_summary": recent_history_summary(jsonl_rows),
        "candidate_reviews": reviews,
        "coverage_snapshot": coverage,
        "production_impact": {
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "trade_enabled": False,
            "parity_note": "No positive alpha was retained. A future positive alpha must be shared-paper-first, default-off if exploratory, and covered by historical replay plus daily snapshot parity before acceptance.",
        },
        "prediction": {
            "success_probability": 0.20,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "all_candidates_frozen",
                "data_surface_insufficient",
                "no_gate4_ready_policy_bundle",
            ],
            "confidence_reason": "Recent accepted edges are narrow and most nearby free-data alpha lanes were just rejected or frozen.",
        },
        "calibration": {
            "actual_decision": "blocked_no_gate4_ready_nonrepeat_alpha_candidate",
            "actual_success": 0,
            "predicted_success_probability": 0.20,
            "brier_score": round((0.20 - 0.0) ** 2, 6),
            "expected_ev_delta": 0.0,
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "realized_failure_mode": "no_gate4_ready_policy_bundle",
            "predicted_failure_mode_hit": True,
        },
        "post_run_reflection": {
            "why_result_happened": "The June 15 incremental history tightened the blocker: Companyfacts quality/growth, SEC text semantics, 13F/Form4, estimate revisions, options/intraday, and OHLCV retunes either have fresh Gate 4 rejections, empty/sparse PIT coverage, or anti-repeat freezes.",
            "why_no_strategy_experiment": "Launching a new policy would either retest a frozen near-neighbor or use an empty/private-only data surface, so any before/after 3-window result would be unreliable and risk production/backtest inconsistency.",
            "why_negative_or_blocked": "This is a negative alpha-selection result, not a bugfix. The failed pre-run hypothesis was that one non-repeat, production-visible, free-data alpha candidate remained ready today.",
            "forbidden_near_neighbor_retry": "Do not retry SEC backlog/order/cost/liquidity keywords, Companyfacts cash-conversion/accrual/asset-growth/profitability/share-count thresholds, 13F low-crowding, Form4/Form144 standalone, OHLCV relabels, or allocator source retunes without materially new PIT fields.",
            "new_evidence_required": "Collect a new free PIT field with all-window coverage: analyst revision breadth/dispersion matched to candidates, customer/supplier contract economics, complete 13F holdings, closed options outcomes, or enough closed true-trigger forward rows for accepted default-off helpers.",
            "best_next_alpha_direction": "Prioritize new data-edge construction over strategy retuning: build PIT analyst revision breadth/dispersion or SEC customer/supplier contract-economics features, then implement shared-paper-first historical replay plus daily default-off parity.",
        },
        "related_files": [
            RUNNER_NAME,
            ARTIFACT_JSON.relative_to(ROOT).as_posix(),
            BEFORE_JSON.relative_to(ROOT).as_posix(),
            AFTER_JSON.relative_to(ROOT).as_posix(),
            ARTIFACT_MD.relative_to(ROOT).as_posix(),
            LOG_PATH.relative_to(ROOT).as_posix(),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return result


def build_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Nonrepeat Alpha Candidate Blocker",
        "",
        "## Decision",
        "",
        f"- Decision: `{result['decision']}`",
        "- Accepted alpha: `false`",
        "- Strategy code changed: `false`",
        "- Production/live impact: `none`",
        "",
        "## Gate 1-4",
        "",
        f"- Gate 1 baseline: `docs/backtesting.md`, aggregate EV `{CANONICAL_BASELINE['aggregate']['expected_value_score']}`, PnL `${CANONICAL_BASELINE['aggregate']['total_pnl']}`.",
        "- Gate 2 fields: no executable rows created; future alpha still requires runtime `entry_date` and `target_price` checks.",
        f"- Gate 3 survival: no filter added; baseline min survival `{CANONICAL_BASELINE['aggregate']['min_survival_rate']}`.",
        "- Gate 4: no behavior changed; all three windows are identical before/after because the alpha launch is blocked.",
        "",
        "| Window | EV Before | EV After | PnL Before | PnL After | Trades | Survival |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in result["gate4"]["by_window"].items():
        lines.append(
            f"| `{name}` | {row['before_expected_value_score']:.4f} | {row['after_expected_value_score']:.4f} | "
            f"${row['before_total_pnl']:.2f} | ${row['after_total_pnl']:.2f} | "
            f"{row['before_trade_count']} | {row['before_survival_rate']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Candidate Reviews",
            "",
            "| Candidate | Decision | Why not run now |",
            "| --- | --- | --- |",
        ]
    )
    for item in result["candidate_reviews"]:
        lines.append(f"| `{item['candidate']}` | `{item['decision']}` | {item['why_not_run']} |")
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            result["post_run_reflection"]["best_next_alpha_direction"],
            "",
            "## Repro",
            "",
            f"- Runner: `{RUNNER_NAME}`",
            f"- JSON artifact: `{ARTIFACT_JSON.relative_to(ROOT).as_posix()}`",
            f"- Before artifact: `{BEFORE_JSON.relative_to(ROOT).as_posix()}`",
            f"- After artifact: `{AFTER_JSON.relative_to(ROOT).as_posix()}`",
            f"- Log: `{LOG_PATH.relative_to(ROOT).as_posix()}`",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_card(result: dict[str, Any]) -> str:
    now = result["timestamp"]
    return f"""---
experiment_id: "{EXPERIMENT_ID}"
status: "blocked"
lane: "alpha_search"
change_type: "alpha_direction_selection"
mechanism_family: "free_data_candidate_pool_prioritization"
trial_family: "alpha_direction_triage"
trial_variant_id: "blocker_scan_v1"
changed_variable: "highest_priority_nonrepeat_alpha_candidate_selection_after_20260615_history_scan_v1"
completed_at: "{now}"
tags:
  - "alpha_search"
  - "blocked"
  - "alpha_direction_selection"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

Closed as blocked after the June 15 history and coverage scan. No strategy code changed and no production/backtest behavior changed.

## Hypothesis

{result["hypothesis"]}

## Gate 1-4

- Gate 1: baseline from `docs/backtesting.md`, aggregate EV `7.8941`, aggregate PnL `$234850.99`.
- Gate 2: no executable rows created; future alpha still requires `entry_date` and `target_price`.
- Gate 3: no filter added; baseline min survival `0.7925`.
- Gate 4: before/after identical across `late_strong`, `mid_weak`, and `old_thin`; launch blocked.

## Decision

`{result["decision"]}`

## Why Blocked

{result["post_run_reflection"]["why_result_happened"]}

## Best Next Direction

{result["post_run_reflection"]["best_next_alpha_direction"]}

## Closeout

- Artifact: `{ARTIFACT_JSON.relative_to(ROOT).as_posix()}`
- Before artifact: `{BEFORE_JSON.relative_to(ROOT).as_posix()}`
- After artifact: `{AFTER_JSON.relative_to(ROOT).as_posix()}`
- Markdown artifact: `{ARTIFACT_MD.relative_to(ROOT).as_posix()}`
- Log: `{LOG_PATH.relative_to(ROOT).as_posix()}`
- Runner: `{RUNNER_NAME}`
- No JavaScript was used.
"""


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_PATH, {})
    ticket.update(
        {
            "status": "blocked",
            "completed_at": result["timestamp"],
            "decision": result["decision"],
            "result": {
                "accepted": False,
                "accepted_alpha": False,
                "decision": result["decision"],
                "artifact": ARTIFACT_JSON.relative_to(ROOT).as_posix(),
                "before_result_file": BEFORE_JSON.relative_to(ROOT).as_posix(),
                "after_result_file": AFTER_JSON.relative_to(ROOT).as_posix(),
                "log": LOG_PATH.relative_to(ROOT).as_posix(),
                "runner": RUNNER_NAME,
                "delta_metrics": result["delta_metrics"],
                "summary": result["post_run_reflection"]["why_result_happened"],
            },
            "gate4": result["gate4"],
            "post_run_reflection": result["post_run_reflection"],
        }
    )
    write_json(TICKET_PATH, ticket)


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = f'"experiment_id": "{EXPERIMENT_ID}"'
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        return
    with path.open("a", encoding="utf-8") as fh:
        if text and not text.endswith("\n"):
            fh.write("\n")
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def write_manifest(result: dict[str, Any]) -> None:
    files = {
        "runner": ROOT / RUNNER_NAME,
        "artifact_json": ARTIFACT_JSON,
        "before_json": BEFORE_JSON,
        "after_json": AFTER_JSON,
        "artifact_md": ARTIFACT_MD,
        "log": LOG_PATH,
        "card": CARD_PATH,
        "ticket": TICKET_PATH,
        "experiment_log": EXPERIMENT_LOG_PATH,
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "decision": result["decision"],
        "git": {
            "branch": git_value("branch", "--show-current"),
            "commit": git_value("rev-parse", "HEAD"),
            "dirty": bool(git_value("status", "--porcelain")),
        },
        "files": {
            key: {
                "path": value.relative_to(ROOT).as_posix(),
                "exists": value.exists(),
                "sha256": sha256(value),
            }
            for key, value in files.items()
        },
    }
    write_json(MANIFEST_PATH, manifest)


def main() -> None:
    result = build_result()
    before = build_backtest_snapshot("before_baseline")
    after = build_backtest_snapshot("after_no_strategy_change")
    write_json(BEFORE_JSON, before)
    write_json(AFTER_JSON, after)
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_PATH, result)
    write_text(ARTIFACT_MD, build_markdown(result))
    update_ticket(result)
    write_text(CARD_PATH, build_card(result))
    append_jsonl_once(EXPERIMENT_LOG_PATH, result)
    write_manifest(result)
    print(json.dumps({"decision": result["decision"], "experiment_id": EXPERIMENT_ID}, sort_keys=True))


if __name__ == "__main__":
    main()
