"""exp-20260617-010: post-reinvestment non-repeat alpha surface readiness.

Alpha-search direction-selection experiment. The single decision hypothesis is
that, after the June 17 asset/reinvestment Companyfacts failures, the next
trustworthy alpha must use a materially new PIT data edge. If the local
three-window surfaces do not expose that edge, launching another strategy
replay would be a frozen-neighbor retune rather than a credible alpha test.

This writes no production strategy code and changes no live/default order,
ranking, sizing, exit, LLM/news, watchlist, or daily-run behavior.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260617-010"
SLUG = "post_reinvestment_nonrepeat_alpha_surface"
RUNNER_NAME = "quant/experiments/exp_20260617_010_post_reinvestment_nonrepeat_alpha_surface.py"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260617_010_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
KOVA_DIR = REPO_ROOT / "data" / "kova"
FORWARD_RV = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
META_REPORT = REPO_ROOT / "data" / "meta_research_report_latest.json"

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

RECENT_EXPERIMENTS = [
    "exp-20260617-003",
    "exp-20260617-004",
    "exp-20260617-005",
    "exp-20260617-006",
    "exp-20260617-007",
    "exp-20260617-008",
    "exp-20260617-009",
    "exp-20260616-027",
    "exp-20260616-028",
    "exp-20260616-015",
    "exp-20260616-018",
]

TAIL_STATE_EXPERIMENTS = [
    "exp-20260609-003",
    "exp-20260609-007",
    "exp-20260609-016",
    "exp-20260610-017",
    "exp-20260610-020",
    "exp-20260610-021",
    "exp-20260611-023",
    "exp-20260613-019",
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
    "duration",
    "counterparty",
    "provenance_hash",
]

REQUIRED_LISTING_FLOAT_FIELDS = [
    "listing_date",
    "ipo_date",
    "de_spac_date",
    "lockup_expiration_date",
    "public_float",
    "float_asof",
]

PREDICTION = {
    "success_probability": 0.10,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "missing_pit_revision_fields",
        "missing_structured_contract_economics",
        "missing_listing_float",
        "options_forward_only",
        "companyfacts_near_neighbors_frozen",
    ],
    "confidence_reason": (
        "Recent alpha logs show D&A, fixed-asset turnover, raw CapEx/D&A, "
        "impairment, and sector-normalized reinvestment are rejected; the "
        "promising alternatives require PIT fields that may not exist locally."
    ),
    "recorded_at": "2026-06-17T08:09:18+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/data-edge: after the June 17 reinvestment/productivity "
        "failures, the only credible next alpha should come from a non-repeated "
        "PIT field such as analyst revision breadth, structured contract "
        "economics, listing/float, options/borrow, or forward replacement rows; "
        "if those fields are absent across the canonical windows, launching "
        "another strategy would be untrustworthy."
    ),
    "2_history_check": {
        "exp-20260617-005_to_009": (
            "D&A burden relief, fixed-asset turnover, raw CapEx/D&A "
            "reinvestment, impairment overhang relief, and sector-normalized "
            "reinvestment productivity all failed Gate 4 or were too sparse."
        ),
        "exp-20260617-004": (
            "Options chain alpha was blocked because local chain rows are "
            "forward-only and do not cover the fixed windows."
        ),
        "exp-20260616-027": (
            "Structured event tuple readiness was blocked; required actor/"
            "object/relation/magnitude fields were absent."
        ),
        "tail_state_family": (
            "Winner-continuation, compression, post-thrust, gap-hold, breadth, "
            "and allocator tail-state variants have already been rejected or "
            "observed-only without stable routing value."
        ),
    },
    "3_single_decision_hypothesis": "post_reinvestment_nonrepeat_alpha_surface_readiness_v1",
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Any strategy launch "
        "must improve aggregate EV/PnL, avoid unacceptable window regression, "
        "keep survival >=5%, have enough trades, control drawdown/concentration, "
        "beat accepted comparators, and use shared helper parity before retention."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260617_010_post_reinvestment_nonrepeat_alpha_surface.py"
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def parse_yyyymmdd(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def parse_iso(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def window_for(day: date | None) -> str | None:
    if day is None:
        return None
    for label, window in CANONICAL_WINDOWS.items():
        if parse_iso(window["start"]) <= day <= parse_iso(window["end"]):
            return label
    return None


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def iter_jsonl(path: Path, max_rows: int | None = None):
    if not path.exists():
        return
    count = 0
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line in handle:
            if max_rows is not None and count >= max_rows:
                break
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                count += 1
                yield row


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = f'"experiment_id": "{EXPERIMENT_ID}"'
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    record_line = json.dumps(record, sort_keys=True)
    if marker in text:
        lines = [record_line if marker in line else line for line in text.splitlines()]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
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


def numeric(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


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
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
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
                after_row["expected_value_score"] - before_row["expected_value_score"],
                6,
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
                after_row["max_drawdown_pct"] - before_row["max_drawdown_pct"],
                6,
            ),
        }
    return {
        "passed": False,
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_surface_after_reinvestment_failures",
        "not_run_reason": "no_strategy_change_after_readiness_blocker",
        "aggregate_expected_value_delta": round(
            after["expected_value_score"] - before["expected_value_score"],
            6,
        ),
        "aggregate_total_pnl_delta": round(after["total_pnl"] - before["total_pnl"], 2),
        "minimum_core_survival_rate": CANONICAL_AGGREGATE["min_survival_rate"],
        "survival_guard_passed": CANONICAL_AGGREGATE["min_survival_rate"] >= 0.05,
        "target_trade_count": 0,
        "target_trade_count_min": 20,
        "target_windows": [],
        "failed_reasons": [
            "missing_pit_revision_breadth_dispersion",
            "missing_structured_contract_economics",
            "missing_listing_lockup_float",
            "options_chain_forward_only_no_fixed_window_rows",
            "finra_borrow_pressure_retired_no_borrow_fee_utilization",
            "companyfacts_asset_reinvestment_neighbors_frozen",
            "tail_state_near_neighbors_rejected_or_observed_only",
            "no_unpromoted_positive_lead_for_shared_adapter",
        ],
        "by_window": by_window,
    }


def summarize_log(exp_id: str) -> dict[str, Any]:
    log_path = REPO_ROOT / "experiments" / "logs" / f"{exp_id}.json"
    row = read_json(log_path, {})
    gate = row.get("gate4") or {}
    reflection = row.get("post_run_reflection") or {}
    if not row:
        return {"experiment_id": exp_id, "found": False, "log": repo_rel(log_path)}
    return {
        "experiment_id": exp_id,
        "found": True,
        "decision": row.get("decision"),
        "status": row.get("status"),
        "aggregate_expected_value_delta": (
            row.get("aggregate_expected_value_delta")
            or row.get("expected_value_score_delta")
            or gate.get("aggregate_ev_delta")
            or gate.get("aggregate_expected_value_delta")
        ),
        "aggregate_pnl_delta": (
            row.get("aggregate_strategy_total_pnl_delta")
            or row.get("total_pnl_delta")
            or gate.get("aggregate_pnl_delta")
            or gate.get("aggregate_total_pnl_delta")
        ),
        "target_trade_count": gate.get("target_trade_count"),
        "target_windows": gate.get("target_windows"),
        "failed_reasons": gate.get("failed_reasons"),
        "forbidden_near_neighbor_retry": reflection.get("forbidden_near_neighbor_retry"),
        "new_evidence_required": reflection.get("new_evidence_required"),
        "log": repo_rel(log_path),
    }


def history_scan() -> dict[str, Any]:
    return {
        "recent_companyfacts_and_data_edge_records": {
            exp_id: summarize_log(exp_id) for exp_id in RECENT_EXPERIMENTS
        },
        "tail_state_records": {exp_id: summarize_log(exp_id) for exp_id in TAIL_STATE_EXPERIMENTS},
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
            columns[table["name"]] = [
                row[1] for row in conn.execute(f"pragma table_info({table['name']})")
            ]
    finally:
        conn.close()
    table_names = [row["name"] for row in tables]
    non_ohlcv_tables = [
        name
        for name in table_names
        if name
        not in {
            "coverage_summary",
            "fetch_status",
            "ohlcv",
            "ohlcv_snapshot_versions",
            "run_manifest",
            "ticker_universe",
        }
    ]
    return {
        "exists": True,
        "path": repo_rel(WAREHOUSE),
        "tables": table_names,
        "non_ohlcv_alpha_tables": non_ohlcv_tables,
        "columns": {name: columns.get(name, []) for name in table_names[:12]},
        "conclusion": (
            "warehouse_has_no_new_non_ohlcv_alpha_surface"
            if not non_ohlcv_tables
            else "warehouse_has_non_ohlcv_tables_review_required"
        ),
    }


def date_token_from_path(path: Path, prefix: str) -> date | None:
    token = path.stem.replace(prefix, "")
    return parse_yyyymmdd(token)


def scan_revision_surface() -> dict[str, Any]:
    files = sorted(NON_OHLCV_DIR.glob("estimate_revision_ledger_*.jsonl"))
    fields: Counter[str] = Counter()
    rows_by_window: Counter[str] = Counter()
    files_by_window: Counter[str] = Counter()
    flags: Counter[str] = Counter()
    rows_with_vendor_asof = 0
    rows_with_any_analyst_count = 0
    rows_with_dispersion = 0
    sampled_rows = 0
    total_rows = 0

    for path in files:
        day = date_token_from_path(path, "estimate_revision_ledger_")
        label = window_for(day) or "outside_fixed_windows"
        files_by_window[label] += 1
        for row in iter_jsonl(path):
            total_rows += 1
            rows_by_window[label] += 1
            if sampled_rows < 2000:
                sampled_rows += 1
                fields.update(row.keys())
                if row.get("vendor_asof"):
                    rows_with_vendor_asof += 1
                if any("analyst" in str(key).lower() and row.get(key) is not None for key in row):
                    rows_with_any_analyst_count += 1
                if any("dispersion" in str(key).lower() and row.get(key) is not None for key in row):
                    rows_with_dispersion += 1
                flags[str(row.get("pit_safe_flag") if "pit_safe_flag" in row else row.get("pit_safe"))] += 1

    field_set = set(fields)
    return {
        "file_count": len(files),
        "files_by_window": dict(files_by_window),
        "total_rows": total_rows,
        "rows_by_window": dict(rows_by_window),
        "sampled_rows": sampled_rows,
        "sampled_field_count": len(field_set),
        "sample_fields": sorted(field_set)[:80],
        "pit_flag_counts_sample": dict(flags),
        "sample_rows_with_vendor_asof": rows_with_vendor_asof,
        "sample_rows_with_any_analyst_count": rows_with_any_analyst_count,
        "sample_rows_with_dispersion": rows_with_dispersion,
        "missing_required_fields": [field for field in REQUIRED_REVISION_FIELDS if field not in field_set],
        "blocked_reason": (
            "Revision ledgers exist, but the required PIT analyst breadth/"
            "dispersion/vendor-asof surface is not available for a trustworthy "
            "three-window candidate-pool replay."
        ),
    }


def scan_options_surface() -> dict[str, Any]:
    files = sorted(NON_OHLCV_DIR.glob("options_onclickmedia_chain_*.jsonl"))
    chain_files_by_window: Counter[str] = Counter()
    rows_by_window: Counter[str] = Counter()
    usable_dates: Counter[str] = Counter()
    rows_with_vendor_asof = 0
    rows_with_open_interest = 0
    total_rows = 0
    first_chain_date: str | None = None
    last_chain_date: str | None = None
    sample_fields: list[str] = []

    for path in files:
        day = date_token_from_path(path, "options_onclickmedia_chain_")
        label = window_for(day) or "outside_fixed_windows"
        if day is not None:
            if first_chain_date is None:
                first_chain_date = day.isoformat()
            last_chain_date = day.isoformat()
        line_count = 0
        for row in iter_jsonl(path):
            line_count += 1
            total_rows += 1
            if not sample_fields:
                sample_fields = sorted(row.keys())
            if row.get("vendor_asof"):
                rows_with_vendor_asof += 1
            if row.get("open_interest") is not None:
                rows_with_open_interest += 1
            if row.get("usable_trade_date"):
                usable_dates[str(row.get("usable_trade_date"))] += 1
        chain_files_by_window[label] += 1
        rows_by_window[label] += line_count

    return {
        "chain_file_count": len(files),
        "chain_files_by_window": dict(chain_files_by_window),
        "rows_by_window": dict(rows_by_window),
        "total_chain_rows": total_rows,
        "first_chain_date": first_chain_date,
        "last_chain_date": last_chain_date,
        "first_usable_trade_date": min(usable_dates) if usable_dates else None,
        "last_usable_trade_date": max(usable_dates) if usable_dates else None,
        "rows_with_vendor_asof": rows_with_vendor_asof,
        "rows_with_open_interest": rows_with_open_interest,
        "sample_fields": sample_fields,
        "fixed_window_chain_rows": sum(rows_by_window.get(label, 0) for label in CANONICAL_WINDOWS),
        "blocked_reason": (
            "Options rows are forward-collected after the fixed windows and "
            "lack vendor_asof, so using them for the canonical replay would "
            "create a production/backtest mismatch."
        ),
    }


def scan_json_fields(paths: list[Path], max_rows_per_file: int = 200) -> Counter[str]:
    fields: Counter[str] = Counter()
    for path in paths:
        if not path.exists():
            continue
        if path.suffix.lower() == ".jsonl":
            for row in iter_jsonl(path, max_rows=max_rows_per_file):
                fields.update(row.keys())
        else:
            obj = read_json(path, {})
            if isinstance(obj, dict):
                fields.update(obj.keys())
                for key in ("events", "records", "items", "data"):
                    rows = obj.get(key)
                    if isinstance(rows, list):
                        for row in rows[:max_rows_per_file]:
                            if isinstance(row, dict):
                                fields.update(row.keys())
    return fields


def scan_structured_event_surface() -> dict[str, Any]:
    paths: list[Path] = []
    paths.extend(sorted(NON_OHLCV_DIR.glob("sec_filing_events_*.jsonl")))
    paths.extend(sorted(NON_OHLCV_DIR.glob("sec_filing_features_*.jsonl")))
    paths.extend(sorted(NON_OHLCV_DIR.glob("sec_filing_text_*.jsonl")))
    paths.extend(sorted((REPO_ROOT / "data" / "daily" / "snapshots" / "events").glob("event_snapshot_*.json")))
    fields = scan_json_fields(paths, max_rows_per_file=150)
    field_set = set(fields)
    present_context = [
        field
        for field in [
            "accepted_at",
            "accepted_datetime",
            "usable_trade_date",
            "event_type",
            "subtype",
            "eight_k_item_type",
            "eight_k_item_codes",
            "title",
            "text_word_count",
            "size",
            "guidance_signal",
        ]
        if field in field_set
    ]
    return {
        "sampled_file_count": len(paths),
        "sampled_field_count": len(field_set),
        "present_context_fields": present_context,
        "missing_required_fields": [
            field for field in REQUIRED_STRUCTURED_EVENT_FIELDS if field not in field_set
        ],
        "blocked_reason": (
            "SEC/event surfaces expose timestamps, item codes, titles, and "
            "some text metadata, but not structured actor/object/relation/"
            "magnitude/value/duration provenance required for a non-generic "
            "contract alpha."
        ),
    }


def scan_listing_float_surface() -> dict[str, Any]:
    paths: list[Path] = []
    paths.extend(sorted(KOVA_DIR.glob("**/*.jsonl")))
    paths.extend(sorted((REPO_ROOT / "data" / "daily" / "universe").glob("universe_state_*.json")))
    paths.extend(sorted((REPO_ROOT / "data" / "daily" / "snapshots").glob("*.json")))
    fields = scan_json_fields(paths, max_rows_per_file=120)
    field_set = set(fields)

    sec13f_files = sorted((KOVA_DIR / "institutional").glob("sec13f_ownership_*.jsonl"))
    sec13f_rows = 0
    sec13f_skipped = 0
    sec13f_sample_fields: Counter[str] = Counter()
    for path in sec13f_files:
        for row in iter_jsonl(path, max_rows=500):
            sec13f_rows += 1
            sec13f_sample_fields.update(row.keys())
            if str(row.get("status") or row.get("reason") or "").lower().find("skip") >= 0:
                sec13f_skipped += 1

    return {
        "sampled_file_count": len(paths),
        "sampled_field_count": len(field_set),
        "missing_required_fields": [
            field for field in REQUIRED_LISTING_FLOAT_FIELDS if field not in field_set
        ],
        "sec13f_file_count": len(sec13f_files),
        "sec13f_sample_rows": sec13f_rows,
        "sec13f_skipped_sample_rows": sec13f_skipped,
        "sec13f_sample_fields": sorted(sec13f_sample_fields)[:80],
        "blocked_reason": (
            "Local surfaces do not provide true listing date, lockup expiration, "
            "public float, or float as-of fields. 13F rows are not a direct "
            "entry alpha and remain delayed/crowding context."
        ),
    }


def scan_forward_replacement_surface() -> dict[str, Any]:
    rows = list(iter_jsonl(FORWARD_RV) or [])
    sleeve_counts: Counter[str] = Counter(str(row.get("sleeve_key") or "unknown") for row in rows)
    enriched_counts: Counter[str] = Counter(
        str(row.get("sleeve_key") or "unknown")
        for row in rows
        if row.get("status") == "enriched"
    )
    positive_counts: Counter[str] = Counter(
        str(row.get("sleeve_key") or "unknown")
        for row in rows
        if row.get("status") == "enriched" and numeric(row.get("replacement_value_vs_cash_usd")) > 0.0
    )
    return {
        "path": repo_rel(FORWARD_RV),
        "exists": FORWARD_RV.exists(),
        "row_count": len(rows),
        "sleeve_counts": dict(sleeve_counts.most_common(12)),
        "enriched_counts": dict(enriched_counts.most_common(12)),
        "positive_counts": dict(positive_counts.most_common(12)),
        "gate4_ready_new_surface": False,
        "blocked_reason": (
            "Closed forward rows, if present, are not a new non-repeat "
            "candidate-pool surface with 20+ independent rows and fixed policy "
            "parity; they are mostly accepted/frozen sleeve observation context."
        ),
    }


def meta_research_summary() -> dict[str, Any]:
    report = read_json(META_REPORT, {})
    strategy_priorities = report.get("strategy_research_priorities") or report.get("research_priorities") or []
    top = []
    if isinstance(strategy_priorities, list):
        for row in strategy_priorities[:5]:
            if isinstance(row, dict):
                top.append(
                    {
                        "family": row.get("family") or row.get("mechanism_family"),
                        "priority": row.get("priority"),
                        "accept_rate": row.get("accept_rate"),
                        "sum_ev_delta": row.get("sum_ev_delta"),
                        "guardrail": row.get("guardrail"),
                    }
                )
    return {
        "path": repo_rel(META_REPORT),
        "records_loaded": report.get("records_loaded"),
        "top_strategy_priorities": top,
        "recommendation_interpretation": (
            "Meta queue still favors production-visible default-off adapters, "
            "but this run found no unpromoted positive lead left after SBC was "
            "shared and the latest reinvestment leads failed."
        ),
    }


def data_surface_audit() -> dict[str, Any]:
    return {
        "warehouse": warehouse_surface(),
        "revision_surface": scan_revision_surface(),
        "options_surface": scan_options_surface(),
        "structured_event_surface": scan_structured_event_surface(),
        "listing_float_surface": scan_listing_float_surface(),
        "forward_replacement_surface": scan_forward_replacement_surface(),
        "meta_research_summary": meta_research_summary(),
    }


def candidate_decisions(surface: dict[str, Any], history: dict[str, Any]) -> list[dict[str, Any]]:
    recent = history["recent_companyfacts_and_data_edge_records"]
    tail = history["tail_state_records"]
    return [
        {
            "candidate": "analyst_revision_breadth_dispersion",
            "decision": "blocked_missing_trustworthy_pit_fields",
            "why_not_run": (
                "Revision ledger rows exist but required analyst-count, revenue "
                "revision, dispersion, fiscal-period, and vendor-asof fields are "
                "missing or not PIT-safe enough for Gate 4."
            ),
            "evidence": surface["revision_surface"],
        },
        {
            "candidate": "structured_customer_supplier_contract_economics",
            "decision": "blocked_missing_structured_relation_tuple",
            "why_not_run": (
                "SEC/event data has item codes and text metadata, but not "
                "actor/object/relation/size/duration/counterparty provenance; "
                "generic SEC text/item families are frozen."
            ),
            "evidence": {
                "surface": surface["structured_event_surface"],
                "history": recent.get("exp-20260616-027"),
            },
        },
        {
            "candidate": "options_or_borrow_pressure_candidate_pool",
            "decision": "blocked_forward_only_or_retired_directional_feed",
            "why_not_run": (
                "Options chains have no fixed-window replay rows and no "
                "vendor_asof; FINRA/IWM borrow-pressure was retired because "
                "directional FINRA labels lacked borrow-fee/utilization edge."
            ),
            "evidence": {
                "options": surface["options_surface"],
                "finra_retirement": recent.get("exp-20260616-028"),
            },
        },
        {
            "candidate": "listing_lockup_float_or_13f_entry",
            "decision": "blocked_missing_listing_float_surface",
            "why_not_run": (
                "No true listing date, lockup expiration, public float, or "
                "float-asof field is available locally; 13F direct-entry is "
                "delayed crowding context and already high-risk."
            ),
            "evidence": surface["listing_float_surface"],
        },
        {
            "candidate": "accepted_helper_tail_state_or_allocator_routing",
            "decision": "blocked_near_neighbors_rejected_or_observed_only",
            "why_not_run": (
                "The requested tail-state buckets around winner continuation, "
                "compression, gap-hold, breadth, post-thrust pause, and "
                "allocator routing were already rejected or observed-only."
            ),
            "evidence": tail,
        },
        {
            "candidate": "companyfacts_asset_reinvestment_quality_retry",
            "decision": "blocked_frozen_after_latest_gate4_failures",
            "why_not_run": (
                "D&A, fixed-asset turnover, raw CapEx/D&A, impairment, and "
                "sector-normalized reinvestment productivity failed Gate 4. "
                "Another tag/threshold/RS/hold/top-N pass would be a frozen "
                "near-neighbor sweep."
            ),
            "evidence": {
                exp_id: recent.get(exp_id)
                for exp_id in [
                    "exp-20260617-005",
                    "exp-20260617-006",
                    "exp-20260617-007",
                    "exp-20260617-008",
                    "exp-20260617-009",
                ]
            },
        },
        {
            "candidate": "shared_default_off_adapter_promotion",
            "decision": "blocked_no_unpromoted_positive_lead",
            "why_not_run": (
                "The highest-priority meta family is shared default-off helper "
                "promotion, but the only recent positive lead (SBC) was already "
                "promoted and the subsequent allocator/per-share/reinvestment "
                "extensions failed."
            ),
            "evidence": {
                "sbc_shared": recent.get("exp-20260616-015"),
                "meta": surface["meta_research_summary"],
            },
        },
    ]


def build_result() -> dict[str, Any]:
    before = baseline_metrics("before_baseline")
    after = baseline_metrics("after_no_strategy_change")
    gate4 = build_gate4(before, after)
    history = history_scan()
    surface = data_surface_audit()
    decisions = candidate_decisions(surface, history)
    timestamp = utc_now()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "blocked",
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_surface_after_reinvestment_failures",
        "lane": "alpha_search",
        "change_type": "nonrepeat_alpha_direction_blocker",
        "mechanism_family": "nonrepeat_alpha_direction_blocker",
        "trial_family": "post_reinvestment_nonrepeat_alpha_surface_readiness",
        "trial_variant_id": "post_reinvestment_nonrepeat_alpha_surface_readiness_v1",
        "single_causal_variable": "post_reinvestment_nonrepeat_alpha_surface_readiness_v1",
        "changed_variable": "post_reinvestment_nonrepeat_alpha_surface_readiness_v1",
        "causal_components": [
            "history scan",
            "local PIT data surface scan",
            "Gate 1-4 no-strategy baseline framing",
            "production parity boundary",
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
        "history_scan": history,
        "data_surface_audit": surface,
        "candidate_decisions": decisions,
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "adapter_status": "analysis_only_no_strategy_or_adapter_change",
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "daily_snapshot_exposed": False,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "uses_llm": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "No strategy, helper, runner, ranking, sizing, exit, watchlist, "
                "LLM/news, or order path changed. Any future positive alpha from "
                "these directions must use one shared default-off helper across "
                "historical replay and daily production observation before "
                "retention."
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
                "The next credible alpha lanes require PIT fields that are not "
                "available across the canonical windows, while executable "
                "near-neighbor strategies are already rejected, accepted/frozen, "
                "or forward-only. A new replay today would be untrustworthy."
            ),
            "negative_reflection": (
                "Forcing another OHLCV, SEC item-code/text, Companyfacts asset/"
                "working-capital/reinvestment, Form4/Form144, FINRA, options, "
                "or tail-state variant would mostly retune frozen windows or "
                "violate production/backtest parity."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry D&A/revenue, fixed-asset turnover, CapEx/D&A, "
                "sector-normalized reinvestment, impairment, inventory/CCC, "
                "generic SEC text/item, Form4/Form144, FINRA, options-chain, "
                "tail-state, 13F, or price-only variants without new PIT fields "
                "or closed forward replacement rows."
            ),
            "best_next_alpha_direction": (
                "Build or collect one real free data edge before the next replay: "
                "PIT analyst revision breadth/dispersion with vendor_asof, "
                "structured customer/supplier contract economics with numeric "
                "value/duration/provenance, independent listing/lockup/float, "
                "historical options/borrow-fee coverage with as-of timestamps, "
                "or enough closed forward replacement rows for a fixed shared "
                "helper."
            ),
        },
        "anti_js": "No JavaScript was used.",
        "reproduction": PRE_RUN_QUESTIONS["5_reproducibility"],
    }


def build_card(result: dict[str, Any]) -> str:
    gate = result["gate4"]
    lines = [
        f"# {EXPERIMENT_ID} Post-Reinvestment Non-Repeat Alpha Surface",
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

    revision = result["data_surface_audit"]["revision_surface"]
    options = result["data_surface_audit"]["options_surface"]
    events = result["data_surface_audit"]["structured_event_surface"]
    listing = result["data_surface_audit"]["listing_float_surface"]
    lines.extend(
        [
            "",
            "## Data Proof",
            "",
            f"- Revision missing fields: `{', '.join(revision['missing_required_fields'])}`",
            f"- Revision PIT flag sample: `{revision['pit_flag_counts_sample']}`",
            f"- Options fixed-window chain rows: `{options['fixed_window_chain_rows']}`",
            f"- Options chain date range: `{options['first_chain_date']} -> {options['last_chain_date']}`",
            f"- Structured-event missing fields: `{', '.join(events['missing_required_fields'])}`",
            f"- Listing/float missing fields: `{', '.join(listing['missing_required_fields'])}`",
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
        "aggregate_expected_value_delta": result["delta_metrics"]["aggregate_expected_value_score"],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
        "gate4": result["gate4"],
        "candidate_decisions": result["candidate_decisions"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": result["anti_js"],
    }


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
        "owner": "alpha-search",
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "causal_components": result["causal_components"],
        "prior_trial_count": 9,
        "nearby_prior_experiments": RECENT_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "three_window_nonrepeat_data_edge_readiness_after_reinvestment_failures",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "decision": result["decision"],
        "summary": result["post_run_reflection"]["why_result_happened"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": result["delta_metrics"]["aggregate_expected_value_score"],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
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
    revision = result["data_surface_audit"]["revision_surface"]
    options = result["data_surface_audit"]["options_surface"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "aggregate_ev_delta": result["delta_metrics"]["aggregate_expected_value_score"],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "revision_missing_fields": revision["missing_required_fields"],
                "options_fixed_window_rows": options["fixed_window_chain_rows"],
                "candidate_decisions": [
                    {"candidate": item["candidate"], "decision": item["decision"]}
                    for item in result["candidate_decisions"]
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
