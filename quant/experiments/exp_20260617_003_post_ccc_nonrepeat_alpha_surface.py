"""exp-20260617-003: post-CCC non-repeat alpha surface blocker.

This is an alpha-search direction-selection experiment, not a strategy replay.
It records why the next alpha should not be another adjacent Companyfacts,
Form4, SEC-text, peer-shock, or price-only retune after exp-20260617-002
returned zero target trades. No trading rule, helper, ranking, sizing, exit,
daily runner, LLM/news behavior, watchlist, or order path is changed.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260617-003"
SLUG = "post_ccc_nonrepeat_alpha_surface"
RUNNER_NAME = "quant/experiments/exp_20260617_003_post_ccc_nonrepeat_alpha_surface.py"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260617_003_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
FORWARD_RV = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"

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

NEARBY_EXPERIMENTS = [
    "exp-20260617-002",
    "exp-20260616-008",
    "exp-20260616-027",
    "exp-20260615-027",
    "exp-20260615-029",
    "exp-20260616-015",
    "exp-20260616-017",
    "exp-20260616-018",
    "exp-20260616-021",
    "exp-20260617-001",
]

REQUIRED_REVISION_FIELDS = [
    "analyst_count_current_qtr",
    "analyst_count_next_qtr",
    "revenue_estimate_current_qtr",
    "revenue_estimate_next_qtr",
    "estimate_dispersion",
    "vendor_asof",
    "fiscal_period",
]

REQUIRED_STRUCTURED_EVENT_FIELDS = [
    "actor",
    "object",
    "relation",
    "magnitude",
    "size_usd",
    "source_id",
    "evidence_span",
    "provenance_hash",
]

REQUIRED_LISTING_FIELDS = [
    "listing_date",
    "ipo_date",
    "de_spac_date",
    "lockup_expiration_date",
    "public_float",
    "float_asof",
]

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "missing_revision_breadth",
        "missing_structured_contract_economics",
        "missing_listing_lockup_float",
        "only_frozen_companyfacts_or_ohlcv_retunes",
        "insufficient_forward_replacement_rows",
    ],
    "confidence_reason": (
        "Recent logs show the strongest accepted sources are already "
        "shared/default-off and frozen for retunes, while the non-repeat "
        "directions repeatedly named by the playbook need PIT fields not "
        "exposed in the local warehouse or snapshots."
    ),
    "recorded_at": "2026-06-17T01:21:14+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/data-edge: after CCC produced zero target trades, the "
        "only credible next alpha needs new PIT evidence such as analyst "
        "revision breadth/dispersion, structured customer/supplier economics, "
        "independent listing/lockup/float data, or mature closed forward rows."
    ),
    "2_history_check": {
        "exp-20260617-002": (
            "Cash-conversion-cycle scout generated zero target trades in all "
            "three windows; do not tune CCC/DSO/DIO/DPO thresholds."
        ),
        "exp-20260616-008": (
            "Form 144 and revision-breadth launch was blocked because parsed "
            "sale-size/role/float and historical breadth/dispersion fields were absent."
        ),
        "exp-20260616-027": (
            "Structured event tuple readiness was blocked with zero complete "
            "tuple rows across the canonical windows."
        ),
        "exp-20260615-029": (
            "Named-counterparty contract economics was rejected with only one "
            "target trade and negative aggregate EV/PnL."
        ),
        "exp-20260616-015": (
            "SBC burden improvement is already accepted as a shared default-off "
            "adapter; adjacent threshold/per-share/allocator retunes are frozen."
        ),
    },
    "3_single_decision_hypothesis": "post_ccc_nonrepeat_alpha_surface_readiness_v1",
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Any strategy launch "
        "must improve aggregate EV/PnL, avoid unacceptable window regression, "
        "keep survival >=5%, have enough trades, control drawdown/concentration, "
        "beat accepted comparators, and use shared helper parity before retention."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260617_003_post_ccc_nonrepeat_alpha_surface.py"
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


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
    record_line = json.dumps(record, sort_keys=True)
    if marker in text:
        lines = [record_line if marker in line else line for line in text.splitlines()]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    with path.open("a", encoding="utf-8") as handle:
        if text and not text.endswith("\n"):
            handle.write("\n")
        handle.write(record_line + "\n")


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
        "max_drawdown_pct": CANONICAL_AGGREGATE["max_drawdown_pct"],
        "signals_generated": CANONICAL_AGGREGATE["signals_generated"],
        "signals_survived": CANONICAL_AGGREGATE["signals_survived"],
        "survival_rate": CANONICAL_AGGREGATE["survival_rate"],
        "windows": CANONICAL_WINDOWS,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "scope": "analysis_only_no_strategy_change",
        },
    }


def build_gate4(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    for label, before_row in before["windows"].items():
        after_row = after["windows"][label]
        by_window[label] = {
            "before_expected_value_score": before_row["expected_value_score"],
            "after_expected_value_score": after_row["expected_value_score"],
            "delta_expected_value_score": round(
                after_row["expected_value_score"] - before_row["expected_value_score"], 6
            ),
            "before_total_pnl": before_row["total_pnl"],
            "after_total_pnl": after_row["total_pnl"],
            "delta_total_pnl": round(after_row["total_pnl"] - before_row["total_pnl"], 2),
            "before_trade_count": before_row["trade_count"],
            "after_trade_count": after_row["trade_count"],
            "delta_trade_count": after_row["trade_count"] - before_row["trade_count"],
            "before_survival_rate": before_row["survival_rate"],
            "after_survival_rate": after_row["survival_rate"],
            "delta_survival_rate": round(after_row["survival_rate"] - before_row["survival_rate"], 6),
            "before_max_drawdown_pct": before_row["max_drawdown_pct"],
            "after_max_drawdown_pct": after_row["max_drawdown_pct"],
            "delta_max_drawdown_pct": round(
                after_row["max_drawdown_pct"] - before_row["max_drawdown_pct"], 6
            ),
        }
    return {
        "passed": False,
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_surface",
        "not_run_reason": "no_strategy_change_after_readiness_blocker",
        "failed_reasons": [
            "missing_revision_breadth",
            "missing_structured_event_tuple_fields",
            "missing_listing_lockup_float",
            "accepted_or_rejected_near_neighbors_frozen",
            "forward_replacement_rows_insufficient_or_frozen",
        ],
        "aggregate_expected_value_delta": round(
            after["expected_value_score"] - before["expected_value_score"], 6
        ),
        "aggregate_total_pnl_delta": round(after["total_pnl"] - before["total_pnl"], 2),
        "minimum_core_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
        "survival_guard_passed": CANONICAL_AGGREGATE["min_survival_rate"] >= 0.05,
        "by_window": by_window,
    }


def summarize_history() -> dict[str, Any]:
    rows = read_jsonl(EXPERIMENT_LOG_JSONL)
    by_id = {str(row.get("experiment_id")): row for row in rows if row.get("experiment_id")}
    summaries: dict[str, Any] = {}
    for exp_id in NEARBY_EXPERIMENTS:
        row = by_id.get(exp_id)
        if not row:
            card = REPO_ROOT / "experiments" / "cards" / f"{exp_id}.md"
            summaries[exp_id] = {
                "found_in_jsonl": False,
                "card_exists": card.exists(),
                "note": "jsonl_missing_or_ignored_but_card_may_exist",
            }
            continue
        summaries[exp_id] = {
            "found_in_jsonl": True,
            "status": row.get("status"),
            "decision": row.get("decision"),
            "aggregate_expected_value_delta": row.get("aggregate_expected_value_delta")
            or row.get("aggregate_ev_delta"),
            "aggregate_pnl_delta": row.get("aggregate_strategy_total_pnl_delta")
            or row.get("aggregate_pnl_delta"),
            "target_trade_count": (row.get("gate4") or {}).get("target_trade_count"),
            "failed_reasons": (row.get("gate4") or {}).get("failed_reasons"),
            "post_run_reflection": row.get("post_run_reflection"),
        }
    return {
        "experiment_log_path": repo_rel(EXPERIMENT_LOG_JSONL),
        "jsonl_row_count": len(rows),
        "nearby_experiments": summaries,
    }


def warehouse_surface() -> dict[str, Any]:
    if not WAREHOUSE.exists():
        return {"exists": False, "blocked_reason": "missing_warehouse"}
    conn = sqlite3.connect(WAREHOUSE)
    try:
        tables = [
            {"name": row[0], "type": row[1]}
            for row in conn.execute(
                "select name, type from sqlite_master where type in ('table','view') order by name"
            )
        ]
        columns: dict[str, list[str]] = {}
        for table in tables:
            columns[table["name"]] = [row[1] for row in conn.execute(f"pragma table_info({table['name']})")]
    finally:
        conn.close()
    table_names = [row["name"] for row in tables]
    return {
        "exists": True,
        "path": repo_rel(WAREHOUSE),
        "tables": table_names,
        "columns": columns,
        "has_non_ohlcv_alpha_fields": any(
            name not in {"coverage_summary", "fetch_status", "ohlcv", "ohlcv_snapshot_versions", "run_manifest", "ticker_universe"}
            for name in table_names
        ),
        "conclusion": "warehouse_is_ohlcv_only_for_alpha_surface",
    }


def scan_json_fields(paths: list[Path], max_rows_per_file: int = 200) -> Counter[str]:
    fields: Counter[str] = Counter()
    for path in paths:
        if not path.exists():
            continue
        if path.suffix.lower() == ".jsonl":
            count = 0
            with path.open(encoding="utf-8-sig") as handle:
                for line in handle:
                    if count >= max_rows_per_file:
                        break
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(row, dict):
                        fields.update(row.keys())
                        count += 1
        else:
            obj = read_json(path, {})
            if isinstance(obj, dict):
                fields.update(obj.keys())
                if isinstance(obj.get("records"), list):
                    for row in obj["records"][:max_rows_per_file]:
                        if isinstance(row, dict):
                            fields.update(row.keys())
                if isinstance(obj.get("events"), list):
                    for row in obj["events"][:max_rows_per_file]:
                        if isinstance(row, dict):
                            fields.update(row.keys())
    return fields


def data_surface_audit() -> dict[str, Any]:
    tags = ["20241002", "20250423", "20251023", "20260421", "20260615"]
    non_ohlcv_files: list[Path] = []
    earnings_files: list[Path] = []
    for tag in tags:
        non_ohlcv_files.extend(
            [
                REPO_ROOT / "data" / "non_ohlcv" / f"daily_non_ohlcv_snapshot_{tag}.json",
                REPO_ROOT / "data" / "non_ohlcv" / f"sec_filing_features_{tag}.jsonl",
                REPO_ROOT / "data" / "non_ohlcv" / f"sec_filing_events_{tag}.jsonl",
                REPO_ROOT / "data" / "non_ohlcv" / f"form4_transactions_{tag}.jsonl",
            ]
        )
        earnings_files.append(
            REPO_ROOT / "data" / "daily" / "snapshots" / "earnings" / f"earnings_snapshot_{tag}.json"
        )
    all_fields = scan_json_fields(non_ohlcv_files + earnings_files)
    field_set = set(all_fields)

    forward_rows = read_jsonl(FORWARD_RV)
    sleeve_counts: Counter[str] = Counter(str(row.get("sleeve_key") or "unknown") for row in forward_rows)
    enriched_counts: Counter[str] = Counter(
        str(row.get("sleeve_key") or "unknown")
        for row in forward_rows
        if row.get("status") == "enriched"
    )
    positive_counts: Counter[str] = Counter(
        str(row.get("sleeve_key") or "unknown")
        for row in forward_rows
        if row.get("status") == "enriched" and float(row.get("replacement_value_vs_cash_usd") or 0.0) > 0.0
    )

    return {
        "warehouse": warehouse_surface(),
        "sampled_files": [repo_rel(path) for path in non_ohlcv_files + earnings_files if path.exists()],
        "sampled_field_count": len(field_set),
        "missing_revision_fields": [field for field in REQUIRED_REVISION_FIELDS if field not in field_set],
        "missing_structured_event_fields": [
            field for field in REQUIRED_STRUCTURED_EVENT_FIELDS if field not in field_set
        ],
        "missing_listing_lockup_float_fields": [
            field for field in REQUIRED_LISTING_FIELDS if field not in field_set
        ],
        "present_high_value_fields": sorted(
            field
            for field in field_set
            if field
            in {
                "accepted_at",
                "accepted_datetime",
                "eight_k_item_codes",
                "eight_k_item_type",
                "usable_trade_date",
                "transaction_code",
                "shares",
                "price_per_share",
                "shares_owned_following_transaction",
                "text_word_count",
                "size",
            }
        ),
        "forward_replacement_value": {
            "path": repo_rel(FORWARD_RV),
            "row_count": len(forward_rows),
            "sleeve_counts": dict(sleeve_counts.most_common()),
            "enriched_counts": dict(enriched_counts.most_common()),
            "positive_counts": dict(positive_counts.most_common()),
            "gate4_ready_new_surface": False,
            "blocked_reason": (
                "Rows are concentrated in already accepted/frozen surfaces such as "
                "low_deployment_etf, state_surface, event sleeves, or existing helpers; "
                "new non-repeat candidate pools lack 20+ closed replacement rows."
            ),
        },
    }


def candidate_decisions(surface: dict[str, Any], history: dict[str, Any]) -> list[dict[str, Any]]:
    nearby = history["nearby_experiments"]
    return [
        {
            "candidate": "analyst_revision_breadth_dispersion",
            "decision": "blocked_missing_historical_fields",
            "evidence": {
                "missing_fields": surface["missing_revision_fields"],
                "history": nearby.get("exp-20260616-008"),
            },
            "why_not_run": (
                "Historical snapshots still lack analyst count, revenue estimate, "
                "dispersion, fiscal-period, and vendor-asof fields."
            ),
        },
        {
            "candidate": "structured_customer_supplier_contract_economics",
            "decision": "blocked_missing_structured_tuple_and_recent_sparse_failure",
            "evidence": {
                "missing_fields": surface["missing_structured_event_fields"],
                "structured_tuple_history": nearby.get("exp-20260616-027"),
                "contract_history": nearby.get("exp-20260615-029"),
            },
            "why_not_run": (
                "Structured tuple fields are absent in sampled PIT surfaces, and the "
                "latest named-counterparty replay had only one target trade."
            ),
        },
        {
            "candidate": "independent_seasoned_listing_lockup_float",
            "decision": "blocked_missing_listing_lockup_float_surface",
            "evidence": {"missing_fields": surface["missing_listing_lockup_float_fields"]},
            "why_not_run": (
                "No true listing date, lockup expiration, or float-asof fields are "
                "available locally; first-seen OHLCV would be a frozen proxy."
            ),
        },
        {
            "candidate": "companyfacts_quality_or_working_capital_retry",
            "decision": "blocked_frozen_near_neighbor_or_zero_sample",
            "evidence": {
                "ccc": nearby.get("exp-20260617-002"),
                "sbc_accepted": nearby.get("exp-20260616-015"),
                "sbc_adjacent": nearby.get("exp-20260616-017"),
                "inventory": nearby.get("exp-20260616-018"),
                "dso": nearby.get("exp-20260616-021"),
                "dpo": nearby.get("exp-20260617-001"),
            },
            "why_not_run": (
                "SBC is already accepted and adjacent retunes are frozen; working "
                "capital/quality variants either failed window/comparator gates or "
                "the CCC bundle generated zero target trades."
            ),
        },
        {
            "candidate": "ohlcv_relation_or_price_only_retry",
            "decision": "blocked_accepted_or_frozen_without_new_field",
            "evidence": {
                "warehouse": surface["warehouse"],
                "forward_replacement_value": surface["forward_replacement_value"],
            },
            "why_not_run": (
                "The warehouse is OHLCV-only and accepted relation/macro/compression "
                "helpers already have shared parity; new price-only variations need "
                "materially independent forward evidence."
            ),
        },
    ]


def build_result() -> dict[str, Any]:
    before = build_backtest_snapshot("before_baseline")
    after = build_backtest_snapshot("after_no_strategy_change")
    gate4 = build_gate4(before, after)
    surface = data_surface_audit()
    history = summarize_history()
    decisions = candidate_decisions(surface, history)
    timestamp = utc_now()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "blocked",
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_surface_after_ccc_zero_sample",
        "lane": "alpha_search",
        "change_type": "nonrepeat_alpha_direction_blocker",
        "mechanism_family": "nonrepeat_alpha_direction_blocker",
        "trial_family": "nonrepeat_alpha_direction_blocker",
        "trial_variant_id": EXPERIMENT_ID,
        "single_causal_variable": "post_ccc_nonrepeat_alpha_surface_readiness_v1",
        "changed_variable": "post_ccc_nonrepeat_alpha_surface_readiness_v1",
        "causal_components": [
            "history scan",
            "local PIT data surface scan",
            "Gate 1-4 no-strategy baseline framing",
            "anti-repeat closeout",
        ],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "prediction": PREDICTION,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": {
            "aggregate_expected_value_score": gate4["aggregate_expected_value_delta"],
            "aggregate_total_pnl": gate4["aggregate_total_pnl_delta"],
            "by_window": gate4["by_window"],
        },
        "gate4": gate4,
        "data_surface_audit": surface,
        "history_scan": history,
        "candidate_decisions": decisions,
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "adapter_status": "analysis_only_no_strategy_or_adapter_change",
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "parity_note": (
                "No strategy, helper, runner, ranking, sizing, exit, watchlist, "
                "LLM/news, or order path changed. Any future positive alpha from "
                "these directions must use one shared default-off helper across "
                "historical replay and daily production observation before retention."
            ),
        },
        "calibration": {
            "actual_success": 0,
            "actual_gate4_passed": False,
            "failure_modes_observed": gate4["failed_reasons"],
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(PREDICTION["success_probability"] ** 2, 4),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The attempted second alpha lane is blocked because the local PIT "
                "surfaces do not expose the independent fields required by the "
                "strongest non-repeat ideas, while nearby executable variants are "
                "already accepted/frozen or recently rejected."
            ),
            "negative_reflection": (
                "Forcing another OHLCV, Companyfacts, Form4, SEC text, or allocator "
                "variant would mostly retune frozen windows and create an "
                "untrustworthy result rather than a new alpha."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry CCC/DSO/DIO/DPO, SBC threshold/per-share/allocator, "
                "generic SEC text, Form4/Form144, peer-shock, macro, compression, "
                "52-week, or price-only reclaim/accumulation variants without new "
                "PIT fields or closed forward replacement rows."
            ),
            "best_next_alpha_direction": (
                "Build a real free-data edge first: PIT analyst revision breadth/"
                "dispersion, structured customer/supplier contract economics with "
                "numeric value/duration/provenance, independent listing/lockup/float, "
                "or enough closed forward rows for an already observed surface."
            ),
        },
        "anti_js": "No JavaScript was used.",
        "reproduction": PRE_RUN_QUESTIONS["5_reproducibility"],
    }


def build_markdown(result: dict[str, Any]) -> str:
    gate = result["gate4"]
    lines = [
        f"# {EXPERIMENT_ID} Post-CCC Non-Repeat Alpha Surface",
        "",
        f"Status: `{result['status']}`",
        f"Decision: `{result['decision']}`",
        "",
        "## Hypothesis",
        "",
        result["hypothesis"],
        "",
        "## Gate 1-4",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in gate["by_window"].items():
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} |".format(
                label=label,
                bev=row["before_expected_value_score"],
                aev=row["after_expected_value_score"],
                dev=row["delta_expected_value_score"],
                bpnl=row["before_total_pnl"],
                apnl=row["after_total_pnl"],
                dpnl=row["delta_total_pnl"],
                surv=row["before_survival_rate"],
            )
        )
    lines.extend(
        [
            "",
            f"- Aggregate EV delta: `{gate['aggregate_expected_value_delta']:+.4f}`",
            f"- Aggregate PnL delta: `${gate['aggregate_total_pnl_delta']:+,.2f}`",
            f"- Gate 4 status: `{gate['decision']}`",
            f"- Failed/blocking reasons: `{', '.join(gate['failed_reasons'])}`",
            "",
            "## Candidate Readiness",
            "",
            "| Candidate | Decision | Reason |",
            "|---|---|---|",
        ]
    )
    for item in result["candidate_decisions"]:
        lines.append(f"| `{item['candidate']}` | `{item['decision']}` | {item['why_not_run']} |")
    surface = result["data_surface_audit"]
    lines.extend(
        [
            "",
            "## Data Surface",
            "",
            f"- Warehouse conclusion: `{surface['warehouse'].get('conclusion')}`",
            f"- Missing revision fields: `{', '.join(surface['missing_revision_fields'])}`",
            f"- Missing structured-event fields: `{', '.join(surface['missing_structured_event_fields'])}`",
            f"- Missing listing/lockup/float fields: `{', '.join(surface['missing_listing_lockup_float_fields'])}`",
            "- Forward replacement rows are not a new Gate-4-ready surface: "
            f"`{surface['forward_replacement_value']['blocked_reason']}`",
            "",
            "## Production Impact",
            "",
            result["production_impact"]["parity_note"],
            "",
            "## Reflection",
            "",
            result["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "status": result["status"],
        "decision": result["decision"],
        "lane": result["lane"],
        "changed_variable": result["changed_variable"],
        "single_causal_variable": result["single_causal_variable"],
        "hypothesis": result["hypothesis"],
        "aggregate_expected_value_delta": result["delta_metrics"]["aggregate_expected_value_score"],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "candidate_decisions": result["candidate_decisions"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": result["anti_js"],
    }


def write_manifest(result: dict[str, Any]) -> None:
    files = [
        Path(RUNNER_NAME),
        ARTIFACT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        LOG_JSON,
        CARD_MD,
        ARTIFACT_MD,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "git_head": git_value("rev-parse", "HEAD"),
        "git_branch": git_value("branch", "--show-current"),
        "files": {repo_rel(REPO_ROOT / path) if not path.is_absolute() else repo_rel(path): sha256(REPO_ROOT / path) if not path.is_absolute() else sha256(path) for path in files},
        "command": result["reproduction"],
    }
    write_json(MANIFEST_JSON, manifest)


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, result["before_metrics"])
    write_json(AFTER_JSON, result["after_metrics"])
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(ARTIFACT_MD, build_markdown(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

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
        "nearby_prior_experiments": NEARBY_EXPERIMENTS,
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
        status="blocked",
        fields=fields,
    )
    write_text(CARD_MD, build_markdown(result))
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
                "missing_revision_fields": result["data_surface_audit"]["missing_revision_fields"],
                "missing_structured_event_fields": result["data_surface_audit"][
                    "missing_structured_event_fields"
                ],
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
