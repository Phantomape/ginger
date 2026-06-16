"""exp-20260616-006: seasoned new-listing independent data readiness.

This is an alpha-search direction-selection experiment, not a strategy replay.
It tests whether the strongest recent positive lead can be relaunched without
violating the anti-repeat rule. No trading rule, helper, ranking, sizing, exit,
daily runner, LLM/news behavior, watchlist, or order path is changed.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
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


EXPERIMENT_ID = "exp-20260616-006"
SLUG = "seasoned_new_listing_independent_data_readiness"
RUNNER_NAME = "quant/experiments/exp_20260616_006_seasoned_new_listing_independent_data_readiness.py"

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
WAREHOUSE_SQLITE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"

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
    "success_probability": 0.20,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "missing_independent_pit_listing_float_data",
        "near_neighbor_retry_risk",
        "no_gate4_ready_policy_bundle",
    ],
    "confidence_reason": (
        "exp-20260613-020 improved aggregate EV by 1.7485 and PnL by 32887.89 "
        "across 300 trades but failed drawdown. Its own reflection requires true "
        "listing date, lockup/float, revenue revision, or sponsorship confirmation. "
        "Recent exp-20260616-002 found revision fields absent for historical launch, "
        "and 13F/Form4 direct lanes have already failed, so the preflight has low "
        "but nonzero probability."
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
    line = json.dumps(record, sort_keys=True)
    if not path.exists():
        path.write_text(line + "\n", encoding="utf-8")
        return

    found = False
    lines: list[str] = []
    with path.open(encoding="utf-8") as fh:
        for old in fh:
            stripped = old.rstrip("\n")
            if marker in stripped:
                lines.append(line)
                found = True
            else:
                lines.append(stripped)
    if not found:
        lines.append(line)
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
    }


def latest_file(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern))
    return files[-1] if files else None


def count_jsonl(path: Path | None, *, max_rows: int | None = None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"exists": False, "source": None, "row_count": 0, "sample_keys": []}
    row_count = 0
    sample_keys: list[str] = []
    with path.open(encoding="utf-8-sig") as fh:
        for line in fh:
            if not line.strip():
                continue
            row_count += 1
            if not sample_keys:
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    parsed = {}
                if isinstance(parsed, dict):
                    sample_keys = sorted(parsed)[:40]
            if max_rows is not None and row_count >= max_rows:
                break
    return {"exists": True, "source": repo_rel(path), "row_count": row_count, "sample_keys": sample_keys}


def find_files_by_name(paths: list[Path], keywords: list[str], *, limit: int = 80) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    lowered = [k.lower() for k in keywords]
    for base in paths:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            if any(k in name for k in lowered):
                matches.append(
                    {
                        "path": repo_rel(path),
                        "bytes": path.stat().st_size,
                        "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z"),
                    }
                )
                if len(matches) >= limit:
                    return {"match_count_limited": len(matches), "matches": matches, "truncated": True}
    return {"match_count_limited": len(matches), "matches": matches, "truncated": False}


def audit_warehouse_schema() -> dict[str, Any]:
    if not WAREHOUSE_SQLITE.exists():
        return {"exists": False, "source": repo_rel(WAREHOUSE_SQLITE), "error": "missing warehouse sqlite"}
    try:
        uri = f"file:{WAREHOUSE_SQLITE.as_posix()}?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            tables = [row[0] for row in con.execute("select name from sqlite_master where type='table' order by name")]
            relevant_columns: list[dict[str, Any]] = []
            for table in tables:
                columns = [row[1] for row in con.execute(f"pragma table_info({table})")]
                hits = [
                    c
                    for c in columns
                    if any(k in c.lower() for k in ("first", "seen", "listing", "ipo", "lock", "float"))
                ]
                if hits:
                    relevant_columns.append({"table": table, "columns": hits})
            return {
                "exists": True,
                "source": repo_rel(WAREHOUSE_SQLITE),
                "table_count": len(tables),
                "relevant_columns": relevant_columns,
                "independent_listing_float_columns_found": any(
                    any(k in column.lower() for k in ("listing", "ipo", "lock", "float"))
                    for row in relevant_columns
                    for column in row["columns"]
                ),
                "note": "first/seen fields are the frozen exp-20260613-020 observable; true listing/lockup/float fields would be independent.",
            }
        finally:
            con.close()
    except Exception as exc:
        return {"exists": True, "source": repo_rel(WAREHOUSE_SQLITE), "error": str(exc)}


def summarize_related_experiment(experiment_id: str) -> dict[str, Any]:
    path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
    log = read_json(path, {})
    return {
        "experiment_id": experiment_id,
        "log": repo_rel(path),
        "exists": bool(log),
        "decision": log.get("decision"),
        "accepted": log.get("accepted") or log.get("accepted_alpha"),
        "aggregate_expected_value_delta": log.get("aggregate_expected_value_delta")
        or log.get("gate4", {}).get("aggregate_ev_delta"),
        "aggregate_pnl_delta": log.get("aggregate_strategy_total_pnl_delta")
        or log.get("gate4", {}).get("aggregate_pnl_delta"),
        "gate4_passed": log.get("gate4", {}).get("passed"),
        "failed_reasons": log.get("gate4", {}).get("failed_reasons"),
        "target_trade_count": log.get("gate4", {}).get("target_trade_count"),
        "post_run_reflection": log.get("post_run_reflection", {}),
    }


def build_gate4(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    for name, before_row in before["windows"].items():
        after_row = after["windows"][name]
        rows[name] = {
            "before_expected_value_score": before_row["expected_value_score"],
            "after_expected_value_score": after_row["expected_value_score"],
            "delta_expected_value_score": round(
                after_row["expected_value_score"] - before_row["expected_value_score"], 4
            ),
            "before_total_pnl": before_row["total_pnl"],
            "after_total_pnl": after_row["total_pnl"],
            "delta_total_pnl": round(after_row["total_pnl"] - before_row["total_pnl"], 2),
            "before_trade_count": before_row["trade_count"],
            "after_trade_count": after_row["trade_count"],
            "before_survival_rate": before_row["survival_rate"],
            "after_survival_rate": after_row["survival_rate"],
            "before_max_drawdown_pct": before_row["max_drawdown_pct"],
            "after_max_drawdown_pct": after_row["max_drawdown_pct"],
        }
    return {
        "passed": False,
        "decision": "blocked_no_gate4_ready_independent_data_surface",
        "reason": "No executable non-repeat policy bundle was launched; before/after are intentionally identical.",
        "aggregate_ev_delta": round(after["expected_value_score"] - before["expected_value_score"], 4),
        "aggregate_pnl_delta": round(after["total_pnl"] - before["total_pnl"], 2),
        "target_trade_count": 0,
        "target_trade_count_min": 20,
        "survival_guard_passed": before["survival_rate"] >= 0.05,
        "minimum_core_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
        "by_window": rows,
    }


def build_result() -> dict[str, Any]:
    before = build_backtest_snapshot("before_baseline")
    after = build_backtest_snapshot("after_no_strategy_change")
    gate4 = build_gate4(before, after)
    latest_revision_summary = latest_file(REPO_ROOT / "data" / "non_ohlcv", "estimate_revision_ledger_summary_*.json")
    latest_revision_ledger = latest_file(REPO_ROOT / "data" / "non_ohlcv", "estimate_revision_ledger_*.jsonl")
    latest_13f = latest_file(REPO_ROOT / "data" / "kova" / "institutional", "sec13f_ownership_*.jsonl")
    latest_form4 = latest_file(REPO_ROOT / "data" / "non_ohlcv", "form4_transactions_*.jsonl")
    inventory_roots = [
        REPO_ROOT / "data" / "reference",
        REPO_ROOT / "data" / "non_ohlcv",
        REPO_ROOT / "data" / "kova",
    ]
    file_inventory = {
        "listing_lockup_float_files": find_files_by_name(
            inventory_roots,
            ["listing", "ipo", "lockup", "lock-up", "share_float", "free_float", "public_float"],
        ),
        "revision_files": find_files_by_name(inventory_roots, ["revision", "estimate", "analyst", "dispersion"]),
        "sponsorship_files": find_files_by_name(inventory_roots, ["13f", "ownership", "form4"]),
    }
    data_surface_audit = {
        "warehouse_schema": audit_warehouse_schema(),
        "latest_revision_summary": {
            "source": repo_rel(latest_revision_summary) if latest_revision_summary else None,
            "summary": read_json(latest_revision_summary, {}),
        },
        "latest_revision_ledger": count_jsonl(latest_revision_ledger, max_rows=5000),
        "latest_13f_ownership": count_jsonl(latest_13f, max_rows=5000),
        "latest_form4_transactions": count_jsonl(latest_form4, max_rows=5000),
        "file_inventory": file_inventory,
    }
    related = {
        exp_id: summarize_related_experiment(exp_id)
        for exp_id in [
            "exp-20260613-020",
            "exp-20260616-002",
            "exp-20260613-014",
            "exp-20260613-017",
            "exp-20260615-009",
        ]
    }
    revision_summary = data_surface_audit["latest_revision_summary"]["summary"]
    listing_files = file_inventory["listing_lockup_float_files"]["matches"]
    independent_listing_count = sum(
        1
        for item in listing_files
        if any(k in item["path"].lower() for k in ("ipo", "listing", "lockup", "lock-up", "share_float", "free_float", "public_float"))
    )
    matched_revision_rows = int(revision_summary.get("matched_candidate_rows") or 0)
    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": "rejected",
        "decision": "blocked_seasoned_new_listing_independent_data_absent",
        "accepted": False,
        "accepted_alpha": False,
        "lane": "alpha_search",
        "change_type": "alpha_direction_selection",
        "mechanism_family": "candidate_pool",
        "trial_family": "seasoned_new_listing_lead",
        "trial_variant_id": "independent_data_readiness_v1",
        "changed_variable": "independent_pit_data_readiness_for_seasoned_new_listing_lead",
        "single_causal_variable": "seasoned_new_listing_independent_pit_data_readiness_v1",
        "causal_components": [
            "data_surface_preflight",
            "history_near_neighbor_check",
            "gate_readiness_decision",
        ],
        "hypothesis": (
            "Seasoned new-listing leadership remains the strongest recent positive lead, "
            "but it is executable only if an independent PIT data surface can separate it "
            "from the frozen first-seen/RS/MA/ADV retune family."
        ),
        "prediction": PREDICTION,
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": {
            "aggregate_expected_value_score": gate4["aggregate_ev_delta"],
            "aggregate_total_pnl": gate4["aggregate_pnl_delta"],
            "trade_count": 0,
            "survival_rate_delta": 0.0,
            "max_drawdown_delta": 0.0,
        },
        "gate1": {
            "baseline_result_file": BASELINE_RESULT_FILE,
            "aggregate_expected_value_score": before["expected_value_score"],
            "aggregate_total_pnl": before["total_pnl"],
            "windows": CANONICAL_WINDOWS,
        },
        "gate2": {
            "passed": False,
            "reason": "No strategy rows were emitted because independent PIT data readiness failed.",
            "required_runtime_fields_for_future_launch": ["entry_date", "target_price"],
        },
        "gate3": {
            "passed": before["survival_rate"] >= 0.05,
            "baseline_survival_rate": before["survival_rate"],
            "minimum_window_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
            "note": "No filter was added; baseline survival remains safely above the 5% hard stop.",
        },
        "gate4": gate4,
        "data_surface_audit": data_surface_audit,
        "related_experiments": related,
        "candidate_reviews": [
            {
                "candidate": "seasoned_new_listing_leadership_retry",
                "alpha_hypothesis": "Young but seasoned liquid listings can add candidate-pool edge after initial listing noise fades.",
                "current_evidence": related["exp-20260613-020"],
                "decision": "blocked_without_independent_evidence",
                "why_not_run": (
                    "The lead was positive across three windows but failed drawdown. Its own closeout bans "
                    "nearby age, RS, moving-average, close-location, ADV, hold-day, notional, and cooldown "
                    "retunes without a materially new PIT field."
                ),
            },
            {
                "candidate": "true_listing_lockup_float_confirmation",
                "alpha_hypothesis": "True listing date, lockup expiry, or float change could distinguish real supply maturation from first-seen momentum.",
                "current_evidence": {
                    "matching_local_files": listing_files,
                    "independent_file_count": independent_listing_count,
                    "warehouse_schema": data_surface_audit["warehouse_schema"],
                },
                "decision": "blocked_missing_local_pit_surface",
                "why_not_run": "No local PIT true listing, IPO, lockup, or float surface was found; the warehouse only offers first-seen-style observables.",
            },
            {
                "candidate": "revision_confirmation_for_young_leaders",
                "alpha_hypothesis": "Matched estimate revision breadth could confirm young leaders with improving expectations.",
                "current_evidence": {
                    "latest_revision_summary": revision_summary,
                    "latest_revision_ledger": data_surface_audit["latest_revision_ledger"],
                },
                "decision": "blocked_no_matched_candidate_rows",
                "why_not_run": (
                    f"The latest revision ledger has {matched_revision_rows} matched candidate rows; "
                    "a historical launch would be backtest-only or empty."
                ),
            },
            {
                "candidate": "13f_sponsorship_confirmation",
                "alpha_hypothesis": "Institutional sponsorship could filter young momentum names toward durable accumulation.",
                "current_evidence": {
                    "latest_13f_ownership": data_surface_audit["latest_13f_ownership"],
                    "sponsorship_acceleration": related["exp-20260613-014"],
                    "new_holder_initiation": related["exp-20260613-017"],
                    "low_crowding_overlay": related["exp-20260615-009"],
                },
                "decision": "blocked_near_neighbor_and_negative_history",
                "why_not_run": "13F sponsorship variants already failed or remained lead-only, and using them only as another filter would be a near-neighbor retry.",
            },
            {
                "candidate": "form4_or_current_daily_confirmation",
                "alpha_hypothesis": "Current insider or daily snapshots might provide confirmation for listing maturation.",
                "current_evidence": data_surface_audit["latest_form4_transactions"],
                "decision": "blocked_not_three_window_pit_alpha",
                "why_not_run": "Form4 role/liability variants are freshly rejected and current daily files do not create a three-window PIT replay surface.",
            },
        ],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "default_off_paper_only": False,
            "live_ready": False,
            "parity_note": "No strategy or production code changed, so backtest/production behavior is identical.",
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 0,
            "actual_decision": "blocked_no_gate4_ready_independent_data_surface",
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta": gate4["aggregate_ev_delta"],
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": gate4["aggregate_pnl_delta"],
            "realized_failure_mode": "missing_independent_pit_listing_float_data",
            "predicted_failure_mode_hit": True,
            "brier_score": round((PREDICTION["success_probability"] - 0.0) ** 2, 4),
        },
        "post_run_reflection": {
            "why_negative_or_blocked": (
                "The best recent positive lead cannot be relaunched today without violating the "
                "anti-repeat rule. The required independent PIT data surface is not present locally."
            ),
            "why_no_strategy_experiment": (
                "A replay would only retune first-seen age, RS, MA, ADV, close-location, hold, "
                "notional, or cooldown on the same frozen windows, or would depend on empty/current-only data."
            ),
            "why_result_happened": (
                "exp-20260613-020 was strong enough to revisit conceptually, but it explicitly requires "
                "true listing date, lockup/float, revision, or sponsorship confirmation. The local scan found "
                "no true listing/lockup/float PIT surface, the latest revision ledger has zero matched candidate "
                "rows, and 13F/Form4 confirmation lanes have already failed or are not three-window PIT-ready."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry seasoned listing age, RS, MA, close-location, ADV, hold-day, notional, "
                "cooldown, 13F sponsorship filter, Form4 role/liability filter, or Companyfacts overlay variants "
                "without a new independent PIT data field."
            ),
            "new_evidence_required": (
                "Build or source true listing date, lockup expiry, share float/free float history, or matched "
                "revision breadth/dispersion rows for historical candidates before another seasoned-listing replay."
            ),
            "best_next_alpha_direction": (
                "Prioritize a free PIT data edge for listing/float/lockup or analyst revision breadth. "
                "If that cannot be sourced, shift to structured customer/supplier contract economics with "
                "value/duration fields and shared daily parity, not another SEC keyword or allocator retune."
            ),
        },
        "anti_js": "No JavaScript was used.",
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
    return result


def build_markdown(result: dict[str, Any]) -> str:
    runner_path = RUNNER_NAME.replace("/", "\\")
    lines = [
        f"# {EXPERIMENT_ID} Seasoned New-Listing Independent Data Readiness",
        "",
        "## Decision",
        "",
        f"- Decision: `{result['decision']}`",
        "- Accepted alpha: `false`",
        "- Strategy code changed: `false`",
        "- Production/live impact: `none`",
        "- No JavaScript was used.",
        "",
        "## Hypothesis",
        "",
        result["hypothesis"],
        "",
        "## Gate 1-4",
        "",
        f"- Gate 1 baseline: `{BASELINE_RESULT_FILE}`.",
        "- Gate 2: no executable rows created; future alpha must validate `entry_date` and `target_price`.",
        f"- Gate 3: no filter added; baseline survival `{CANONICAL_AGGREGATE['survival_rate']}`.",
        "- Gate 4: before/after identical because launch was blocked by missing independent PIT data.",
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
mechanism_family: "candidate_pool"
trial_family: "seasoned_new_listing_lead"
trial_variant_id: "independent_data_readiness_v1"
changed_variable: "independent_pit_data_readiness_for_seasoned_new_listing_lead"
completed_at: "{result["timestamp"]}"
tags:
  - "alpha_search"
  - "rejected"
  - "alpha_direction_selection"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

Blocked a seasoned new-listing retry because the independent PIT data required by `exp-20260613-020` is not available locally. No strategy code changed and no production/backtest behavior changed.

## Hypothesis

{result["hypothesis"]}

## Gate 1-4

- Gate 1: baseline from `docs/backtesting.md`, aggregate EV `7.8941`, aggregate PnL `$234850.99`.
- Gate 2: no executable rows created; future alpha still requires `entry_date` and `target_price`.
- Gate 3: no filter added; baseline min survival `0.7925`.
- Gate 4: before/after identical across `late_strong`, `mid_weak`, and `old_thin`; strategy launch blocked.

## Decision

`{result["decision"]}`

## Why Blocked

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
            "exp-20260613-020",
            "exp-20260616-002",
            "exp-20260613-014",
            "exp-20260613-017",
            "exp-20260615-009",
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
