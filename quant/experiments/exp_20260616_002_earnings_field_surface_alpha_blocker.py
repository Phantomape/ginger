"""exp-20260616-002: earnings-field and surface alpha blocker scan.

This is an alpha-search direction-selection experiment, not a strategy replay.
It tests whether a non-repeat free-data alpha can be launched after the latest
June 15 blockers. No trading rule, helper, ranking, sizing, exit, LLM/news
behavior, watchlist, or order path is changed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260616-002"
SLUG = "earnings_field_surface_alpha_blocker"
RUNNER_NAME = "quant/experiments/exp_20260616_002_earnings_field_surface_alpha_blocker.py"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"

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

PREDICTION = {
    "success_probability": 0.10,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "all_candidates_frozen",
        "data_surface_insufficient",
        "no_gate4_ready_policy_bundle",
    ],
    "confidence_reason": (
        "Recent blockers already removed SEC text, Companyfacts, 13F/Form4, "
        "options/intraday, Space, and allocator retune lanes; this run checks "
        "whether earnings snapshots expose the missing analyst breadth or "
        "dispersion fields."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = f'"experiment_id": "{EXPERIMENT_ID}"'
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    line = json.dumps(record, sort_keys=True)
    if marker not in text:
        with path.open("a", encoding="utf-8") as fh:
            if text and not text.endswith("\n"):
                fh.write("\n")
            fh.write(line + "\n")
        return
    lines = [line if marker in old else old for old in text.splitlines()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return proc.stdout.strip()


def build_backtest_snapshot(label: str) -> dict[str, Any]:
    return {
        "label": label,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "expected_value_score": CANONICAL_AGGREGATE["expected_value_score"],
        "total_pnl": CANONICAL_AGGREGATE["total_pnl"],
        "total_trades": CANONICAL_AGGREGATE["trade_count"],
        "signals_generated": CANONICAL_AGGREGATE["signals_generated"],
        "signals_survived": CANONICAL_AGGREGATE["signals_survived"],
        "survival_rate": CANONICAL_AGGREGATE["survival_rate"],
        "max_drawdown_pct": CANONICAL_AGGREGATE["max_drawdown_pct"],
        "windows": CANONICAL_WINDOWS,
    }


def latest_file(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern))
    return files[-1] if files else None


def count_jsonl(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"exists": False, "source": None, "row_count": 0, "usable_rows": 0, "skipped_rows": 0, "sample_keys": []}
    row_count = 0
    usable = 0
    skipped = 0
    sample_keys: list[str] = []
    with path.open(encoding="utf-8-sig") as fh:
        for line in fh:
            if not line.strip():
                continue
            row_count += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not sample_keys and isinstance(row, dict):
                sample_keys = sorted(row.keys())[:30]
            status = str(row.get("status") or "").lower() if isinstance(row, dict) else ""
            reason = str(row.get("reason") or "").lower() if isinstance(row, dict) else ""
            if status in {"skipped", "error", "unavailable"} or reason:
                skipped += 1
            else:
                usable += 1
    return {
        "exists": True,
        "source": repo_rel(path),
        "row_count": row_count,
        "usable_rows": usable,
        "skipped_rows": skipped,
        "sample_keys": sample_keys,
    }


def audit_earnings_snapshots() -> dict[str, Any]:
    root = REPO_ROOT / "data" / "daily" / "snapshots" / "earnings"
    files = sorted(root.glob("earnings_snapshot_*.json"))
    required_new_fields = [
        "analyst_count_current_qtr",
        "analyst_count_next_qtr",
        "revenue_estimate_current_qtr",
        "revenue_estimate_next_qtr",
        "estimate_dispersion",
        "vendor_asof",
        "fiscal_period",
    ]
    by_window: dict[str, Any] = {}
    for label, window in CANONICAL_WINDOWS.items():
        start_tag = window["start"].replace("-", "")
        end_tag = window["end"].replace("-", "")
        window_files = [
            path
            for path in files
            if start_tag <= path.stem[-8:] <= end_tag
        ]
        by_window[label] = {
            "snapshot_files": len(window_files),
            "first_snapshot": repo_rel(window_files[0]) if window_files else None,
            "last_snapshot": repo_rel(window_files[-1]) if window_files else None,
        }

    probe_tags = ["20241002", "20250423", "20251023", "20260421", "20260614"]
    probes: dict[str, Any] = {}
    aggregate_field_counts: dict[str, int] = {}
    aggregate_rows = 0
    missing_new_fields: set[str] = set(required_new_fields)
    for tag in probe_tags:
        path = root / f"earnings_snapshot_{tag}.json"
        payload = read_json(path, {})
        earnings = payload.get("earnings") if isinstance(payload, dict) else {}
        earnings = earnings if isinstance(earnings, dict) else {}
        key_counts: dict[str, int] = {}
        for row in earnings.values():
            if not isinstance(row, dict):
                continue
            aggregate_rows += 1
            for key in row:
                key_counts[key] = key_counts.get(key, 0) + 1
                aggregate_field_counts[key] = aggregate_field_counts.get(key, 0) + 1
                missing_new_fields.discard(key)
        probes[tag] = {
            "exists": path.exists(),
            "source": repo_rel(path),
            "ticker_rows": len(earnings),
            "field_counts": dict(sorted(key_counts.items())),
            "required_new_fields_present": {
                field: field in key_counts for field in required_new_fields
            },
        }

    return {
        "snapshot_dir": repo_rel(root),
        "file_count": len(files),
        "first_snapshot": repo_rel(files[0]) if files else None,
        "last_snapshot": repo_rel(files[-1]) if files else None,
        "by_window": by_window,
        "probe_snapshots": probes,
        "aggregate_probe_rows": aggregate_rows,
        "aggregate_probe_field_counts": dict(sorted(aggregate_field_counts.items())),
        "required_new_fields": required_new_fields,
        "missing_required_new_fields": sorted(missing_new_fields),
        "decision_relevance": (
            "Historical snapshots cover all three windows, but expose only EPS estimate, "
            "days-to-earnings, last actual EPS, and surprise history in the canonical windows. "
            "They do not contain analyst count, revenue estimate, dispersion, fiscal-period, "
            "or vendor-as-of fields needed for a non-repeat revision alpha."
        ),
    }


def log_summary(experiment_id: str) -> dict[str, Any]:
    path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
    payload = read_json(path, {})
    if not isinstance(payload, dict):
        return {"experiment_id": experiment_id, "exists": False, "path": repo_rel(path)}
    aggregate = payload.get("aggregate") or payload.get("aggregate_delta_vs_core") or {}
    delta = payload.get("delta_metrics") or {}
    return {
        "experiment_id": experiment_id,
        "exists": True,
        "path": repo_rel(path),
        "status": payload.get("status"),
        "decision": payload.get("decision"),
        "changed_variable": payload.get("changed_variable"),
        "aggregate": aggregate,
        "delta_metrics": delta,
        "post_run_reflection": payload.get("post_run_reflection", {}),
    }


def audit_surfaces() -> dict[str, Any]:
    non_ohlcv = REPO_ROOT / "data" / "non_ohlcv"
    kova = REPO_ROOT / "data" / "kova"
    options_summary = latest_file(non_ohlcv, "options_onclickmedia_summary_*.json")
    estimate_summary = latest_file(non_ohlcv, "estimate_revision_ledger_summary_*.json")
    form4_summary = latest_file(non_ohlcv, "form4_backfill_summary_*.json")
    space_runners = sorted((REPO_ROOT / "quant" / "experiments").glob("exp_*_space_*.py"))

    return {
        "earnings_snapshots": audit_earnings_snapshots(),
        "estimate_revision_latest_summary": read_json(estimate_summary, {}) if estimate_summary else {},
        "estimate_revision_latest_summary_path": repo_rel(estimate_summary) if estimate_summary else None,
        "form4_latest_summary": read_json(form4_summary, {}) if form4_summary else {},
        "form4_latest_summary_path": repo_rel(form4_summary) if form4_summary else None,
        "options_latest_summary": read_json(options_summary, {}) if options_summary else {},
        "options_latest_summary_path": repo_rel(options_summary) if options_summary else None,
        "kova_sec13f_latest": count_jsonl(latest_file(kova / "institutional", "sec13f_ownership_*.jsonl")),
        "kova_intraday_latest": count_jsonl(latest_file(kova / "intraday", "intraday_ohlcv_*.jsonl")),
        "kova_companyfacts_latest": count_jsonl(latest_file(kova / "fundamentals", "companyfacts_growth_*.jsonl")),
        "space_experiment_runner_count": len(space_runners),
        "space_latest_runners": [repo_rel(path) for path in space_runners[-10:]],
        "nearby_logs": {
            exp_id: log_summary(exp_id)
            for exp_id in [
                "exp-20260615-014",
                "exp-20260615-015",
                "exp-20260615-027",
                "exp-20260615-024",
                "exp-20260613-025",
                "exp-20260615-029",
                "exp-20260609-011",
            ]
        },
    }


def build_candidate_reviews(surface: dict[str, Any]) -> list[dict[str, Any]]:
    earnings = surface["earnings_snapshots"]
    estimate = surface["estimate_revision_latest_summary"]
    options_log = surface["nearby_logs"]["exp-20260613-025"]
    form4_log = surface["nearby_logs"]["exp-20260615-024"]
    contract_log = surface["nearby_logs"]["exp-20260615-029"]
    return [
        {
            "candidate": "pit_analyst_revision_breadth_dispersion",
            "alpha_hypothesis": (
                "Analyst-count breadth, revenue-estimate velocity, or dispersion compression "
                "could rank expectation-underreaction candidates better than EPS-only revision."
            ),
            "decision": "blocked_missing_required_historical_fields",
            "current_evidence": {
                "historical_earnings_snapshot_field_audit": earnings,
                "latest_forward_revision_summary": estimate,
            },
            "history_check": ["exp-20260609-011", "exp-20260610-014", "exp-20260615-014", "exp-20260615-027"],
            "why_not_run": (
                "The historical snapshots cover the windows but lack analyst-count, revenue-estimate, "
                "dispersion, fiscal-period, and vendor-as-of fields. EPS-only revision is already the "
                "accepted default-off revision helper, so a replay would be a frozen retune."
            ),
            "retry_requires": (
                "Persist analyst-count, revenue estimate, dispersion, fiscal-period, and source "
                "freshness with all-window or forward replacement coverage."
            ),
        },
        {
            "candidate": "form4_role_or_cluster_candidate_pool",
            "alpha_hypothesis": "Insider open-market buying may reveal informed demand if quality or role filters isolate conviction.",
            "decision": "blocked_recent_negative_and_near_neighbor_frozen",
            "current_evidence": form4_log,
            "history_check": ["exp-20260615-024", "exp-20260614-018", "exp-20260614-019"],
            "why_not_run": (
                "The latest CEO/CFO/President plus low-liability Form4 replay was negative versus core "
                "across all three canonical windows; nearby role, threshold, cluster, and conviction "
                "retunes are explicitly frozen without a new relation-quality field."
            ),
            "retry_requires": "Forward closed paper outcomes or a new PIT field such as buy-size relative to holdings/compensation.",
        },
        {
            "candidate": "options_or_intraday_free_data_edge",
            "alpha_hypothesis": "Option structure or intraday thrust could add a market-implied edge unavailable in daily OHLCV.",
            "decision": "blocked_no_closed_options_outcomes_and_intraday_skipped",
            "current_evidence": {
                "options_closed_outcome_log": options_log,
                "kova_intraday_latest": surface["kova_intraday_latest"],
            },
            "history_check": ["exp-20260613-025", "exp-20260506-009"],
            "why_not_run": (
                "Options remain shadow-only with zero closed candidate outcomes in the latest overlay, "
                "while Kova intraday rows are skipped/unusable for canonical historical replay."
            ),
            "retry_requires": "Closed option-tagged forward outcomes or PIT-safe intraday backfill across all windows.",
        },
        {
            "candidate": "sec13f_or_ownership_candidate_pool",
            "alpha_hypothesis": "Ownership/crowding relief could improve candidate-pool selection beyond price leadership.",
            "decision": "blocked_empty_surface_and_recent_rejection",
            "current_evidence": surface["kova_sec13f_latest"],
            "history_check": ["exp-20260615-009", "exp-20260613-014", "exp-20260613-026"],
            "why_not_run": (
                "The latest Kova 13F surface has skipped or unusable rows, and the recent low-crowding "
                "leadership scout failed the three-window gate."
            ),
            "retry_requires": "Mapped PIT 13F holdings with all-window issuer coverage and manager/sector-normalized surprise fields.",
        },
        {
            "candidate": "space_catalyst_theme_candidate_pool",
            "alpha_hypothesis": "Official space catalysts plus theme/peer context could expand the candidate pool without generic ticker noise.",
            "decision": "blocked_saturated_forward_only_theme_surface",
            "current_evidence": {
                "space_experiment_runner_count": surface["space_experiment_runner_count"],
                "latest_runners": surface["space_latest_runners"],
            },
            "history_check": ["space_catalyst_sleeve", "docs/production_backtest_parity_matrix.md"],
            "why_not_run": (
                "Space already has a shared observe-only surface with many metadata/risk helpers; "
                "promotion requires closed replacement evidence, not another historical theme retune."
            ),
            "retry_requires": "Closed forward replacement rows from the shared Space ledger and a separate promotion experiment.",
        },
        {
            "candidate": "sec_customer_supplier_contract_economics",
            "alpha_hypothesis": "Structured customer/supplier identity and contract economics could beat generic SEC text signals.",
            "decision": "blocked_latest_named_counterparty_replay_failed",
            "current_evidence": contract_log,
            "history_check": ["exp-20260615-029", "exp-20260615-011", "exp-20260615-012", "exp-20260615-013"],
            "why_not_run": (
                "The named-counterparty contract-economics replay produced only one target trade and "
                "negative aggregate EV/PnL; generic SEC text demand/backlog variants are also frozen."
            ),
            "retry_requires": "A persisted structured counterparty field with value, duration, renewal, or margin economics.",
        },
        {
            "candidate": "ohlcv_or_allocator_retune",
            "alpha_hypothesis": "A price/volume or accepted-helper allocator retune might still improve source choice.",
            "decision": "blocked_all_candidates_frozen",
            "current_evidence": {"accepted_allocator": log_summary("exp-20260611-005")},
            "history_check": ["exp-20260613-004", "exp-20260613-006", "exp-20260613-009", "exp-20260613-015"],
            "why_not_run": (
                "Accepted allocator rank/top-N/notional/hold/cooldown and price-only relabels are frozen "
                "without a materially new PIT field or forward displacement evidence."
            ),
            "retry_requires": "New source data, not a source-priority or OHLCV threshold sweep.",
        },
    ]


def gate4_snapshot(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, Any] = {}
    for label, row in CANONICAL_WINDOWS.items():
        by_window[label] = {
            "before_expected_value_score": row["expected_value_score"],
            "after_expected_value_score": row["expected_value_score"],
            "delta_expected_value_score": 0.0,
            "before_total_pnl": row["total_pnl"],
            "after_total_pnl": row["total_pnl"],
            "delta_total_pnl": 0.0,
            "before_trade_count": row["trade_count"],
            "after_trade_count": row["trade_count"],
            "delta_trade_count": 0,
            "before_survival_rate": row["survival_rate"],
            "after_survival_rate": row["survival_rate"],
            "delta_survival_rate": 0.0,
            "before_max_drawdown_pct": row["max_drawdown_pct"],
            "after_max_drawdown_pct": row["max_drawdown_pct"],
            "delta_max_drawdown_pct": 0.0,
        }
    return {
        "applicable": False,
        "reason": (
            "No strategy policy was launched because every reviewed direction failed anti-repeat, "
            "PIT field coverage, forward sample, or production/backtest parity readiness checks."
        ),
        "aggregate_before": {
            "expected_value_score": before["expected_value_score"],
            "total_pnl": before["total_pnl"],
            "trade_count": before["total_trades"],
            "survival_rate": before["survival_rate"],
            "max_drawdown_pct": before["max_drawdown_pct"],
        },
        "aggregate_after": {
            "expected_value_score": after["expected_value_score"],
            "total_pnl": after["total_pnl"],
            "trade_count": after["total_trades"],
            "survival_rate": after["survival_rate"],
            "max_drawdown_pct": after["max_drawdown_pct"],
        },
        "aggregate_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "survival_rate": 0.0,
            "max_drawdown_pct": 0.0,
        },
        "by_window": by_window,
    }


def build_result() -> dict[str, Any]:
    before = build_backtest_snapshot("before_baseline")
    after = build_backtest_snapshot("after_no_strategy_change")
    surface = audit_surfaces()
    reviews = build_candidate_reviews(surface)
    gate4 = gate4_snapshot(before, after)
    now = utc_now()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": "blocked",
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_candidate",
        "accepted": False,
        "accepted_alpha": False,
        "lane": "alpha_search",
        "change_type": "alpha_direction_selection",
        "mechanism_family": "free_data_candidate_pool_prioritization",
        "trial_family": "alpha_direction_triage",
        "trial_variant_id": "blocker_scan_v4",
        "changed_variable": "highest_priority_nonrepeat_alpha_candidate_selection_after_earnings_field_and_theme_surface_scan_v1",
        "single_causal_variable": "highest_priority_nonrepeat_alpha_candidate_selection_after_earnings_field_and_theme_surface_scan_v1",
        "causal_components": [
            "history_scan",
            "data_surface_coverage_check",
            "anti_repeat_gate",
            "gate4_applicability_decision",
        ],
        "hypothesis": (
            "After the latest June 15 blockers and this run's data scan, a non-repeat free-data alpha may "
            "still be launchable only if it has canonical three-window PIT coverage, a materially new field, "
            "and a shared-paper-first path."
        ),
        "anti_js": "No JavaScript was used.",
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "trade_count": 0,
            "survival_rate": 0.0,
            "max_drawdown_pct": 0.0,
        },
        "gate1": {
            "baseline_result_file": BASELINE_RESULT_FILE,
            "core_baseline_metrics": CANONICAL_WINDOWS,
            "aggregate_baseline": CANONICAL_AGGREGATE,
        },
        "gate2": {
            "passed": False,
            "reason": "No executable strategy rows were created; future alpha still must validate entry_date and target_price.",
            "missing_entry_date_or_target_price": [],
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "min_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
            "survival_rate": CANONICAL_AGGREGATE["survival_rate"],
        },
        "gate4": gate4,
        "coverage_snapshot": surface,
        "candidate_reviews": reviews,
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": "blocked_no_gate4_ready_nonrepeat_alpha_candidate",
            "actual_success": 0,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "predicted_success_probability": PREDICTION["success_probability"],
            "predicted_failure_mode_hit": True,
            "realized_failure_mode": "no_gate4_ready_policy_bundle",
            "brier_score": round((PREDICTION["success_probability"] - 0.0) ** 2, 6),
        },
        "production_impact": {
            "strategy_code_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "trade_enabled": False,
            "parity_note": (
                "No positive alpha was retained. A future positive alpha must be shared-paper-first "
                "and daily/default-off parity covered before acceptance."
            ),
        },
        "post_run_reflection": {
            "why_negative_or_blocked": (
                "This is a negative alpha-selection result. The pre-run hypothesis that one non-repeat, "
                "production-visible, free-data alpha candidate remained launchable today failed."
            ),
            "why_no_strategy_experiment": (
                "Running a strategy replay today would either retest a frozen near-neighbor or rely on "
                "an incomplete/backtest-only data surface, so the result would not be trustworthy."
            ),
            "why_result_happened": (
                "The extra scan closed the most plausible gap: historical earnings snapshots cover all "
                "three windows but do not contain analyst breadth, revenue revision, dispersion, fiscal-period, "
                "or vendor-as-of fields. The remaining Form4, options, 13F, Space, SEC text, and allocator lanes "
                "are either freshly negative, forward-only, empty/skipped, or explicitly frozen."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry EPS-only revision thresholds/rank, Form4 role/liability/cluster filters, "
                "options joins without closed outcomes, 13F low-crowding, Space theme retunes, generic SEC text, "
                "or accepted allocator priority/top-N/cooldown/notional changes without materially new PIT evidence."
            ),
            "new_evidence_required": (
                "Build a new free PIT data edge first: analyst-count/revenue/dispersion/provenance rows "
                "matched to historical candidates, structured customer/supplier contract economics, usable "
                "13F holdings, closed options outcomes, or enough true-trigger forward replacement rows."
            ),
            "best_next_alpha_direction": (
                "Prioritize analyst revision breadth/dispersion data construction, not strategy retuning. "
                "If that cannot be sourced, the next best alpha search is structured SEC counterparty economics "
                "with value/duration fields and shared daily parity."
            ),
        },
        "related_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(ARTIFACT_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
        ],
    }


def build_markdown(result: dict[str, Any]) -> str:
    runner_path = RUNNER_NAME.replace("/", "\\")
    lines = [
        f"# {EXPERIMENT_ID} Earnings Field Surface Alpha Blocker",
        "",
        "## Decision",
        "",
        f"- Decision: `{result['decision']}`",
        "- Accepted alpha: `false`",
        "- Strategy code changed: `false`",
        "- Production/live impact: `none`",
        "- No JavaScript was used.",
        "",
        "## Gate 1-4",
        "",
        f"- Gate 1 baseline: `{BASELINE_RESULT_FILE}`.",
        "- Gate 2: no executable rows created; future alpha must validate `entry_date` and `target_price`.",
        f"- Gate 3: no filter added; baseline survival `{CANONICAL_AGGREGATE['survival_rate']}`.",
        "- Gate 4: before/after identical because launch was rejected.",
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
    lines.extend(["", "## Candidate Reviews", "", "| Candidate | Decision | Why not run now |", "| --- | --- | --- |"])
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
            f"```powershell\n.\\.venv\\Scripts\\python.exe -B {runner_path}\n```",
            "",
        ]
    )
    return "\n".join(lines)


def build_card(result: dict[str, Any]) -> str:
    return f"""---
experiment_id: "{EXPERIMENT_ID}"
status: "rejected"
lane: "alpha_search"
change_type: "alpha_direction_selection"
mechanism_family: "free_data_candidate_pool_prioritization"
trial_family: "alpha_direction_triage"
trial_variant_id: "blocker_scan_v4"
changed_variable: "highest_priority_nonrepeat_alpha_candidate_selection_after_earnings_field_and_theme_surface_scan_v1"
completed_at: "{result["timestamp"]}"
tags:
  - "alpha_search"
  - "rejected"
  - "alpha_direction_selection"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

Rejected launch after checking historical earnings fields plus recent Form4, options, 13F, Space, SEC text, and allocator lanes. No strategy code changed and no production/backtest behavior changed.

## Hypothesis

{result["hypothesis"]}

## Gate 1-4

- Gate 1: baseline from `docs/backtesting.md`, aggregate EV `7.8941`, aggregate PnL `$234850.99`.
- Gate 2: no executable rows created; future alpha still requires `entry_date` and `target_price`.
- Gate 3: no filter added; baseline min survival `0.7925`.
- Gate 4: before/after identical across `late_strong`, `mid_weak`, and `old_thin`; strategy launch rejected.

## Decision

`{result["decision"]}`

## Why Rejected

{result["post_run_reflection"]["why_result_happened"]}

## Best Next Direction

{result["post_run_reflection"]["best_next_alpha_direction"]}

## Closeout

- Artifact: `{repo_rel(ARTIFACT_JSON)}`
- Before artifact: `{repo_rel(BEFORE_JSON)}`
- After artifact: `{repo_rel(AFTER_JSON)}`
- Markdown artifact: `{repo_rel(ARTIFACT_MD)}`
- Log: `{repo_rel(LOG_JSON)}`
- Runner: `{RUNNER_NAME}`
- No JavaScript was used.
"""


def write_manifest(result: dict[str, Any]) -> None:
    files = {
        "runner": REPO_ROOT / RUNNER_NAME,
        "artifact_json": ARTIFACT_JSON,
        "before_json": BEFORE_JSON,
        "after_json": AFTER_JSON,
        "artifact_md": ARTIFACT_MD,
        "log": LOG_JSON,
        "card": CARD_MD,
        "ticket": TICKET_JSON,
        "experiment_log": EXPERIMENT_LOG_JSONL,
        "registry": REGISTRY_JSON,
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
            key: {"path": repo_rel(value), "exists": value.exists(), "sha256": sha256(value)}
            for key, value in files.items()
        },
    }
    write_json(MANIFEST_JSON, manifest)


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, result["before_metrics"])
    write_json(AFTER_JSON, result["after_metrics"])
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(ARTIFACT_MD, build_markdown(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, result)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before_result_file": repo_rel(BEFORE_JSON),
        "after_result_file": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "single_causal_variable": result["single_causal_variable"],
        "causal_components": result["causal_components"],
        "nearby_prior_experiments": [
            "exp-20260615-014",
            "exp-20260615-015",
            "exp-20260615-027",
            "exp-20260615-024",
            "exp-20260613-025",
            "exp-20260615-029",
        ],
        "baseline_result_file": BASELINE_RESULT_FILE,
        "post_run_reflection": result["post_run_reflection"],
        "gate4": result["gate4"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=registry_result,
        status="rejected",
        fields=fields,
    )
    write_text(CARD_MD, build_card(result))
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
                "aggregate_ev_delta": result["delta_metrics"]["aggregate_expected_value_score"],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "best_next_alpha_direction": result["post_run_reflection"]["best_next_alpha_direction"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
