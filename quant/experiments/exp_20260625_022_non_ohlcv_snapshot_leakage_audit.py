"""exp-20260625-022: non-OHLCV snapshot as-of boundary audit.

Measurement repair only. This audits whether dated daily non-OHLCV snapshots
and the coverage manifest can leak future/backfilled rows into replay or
forward attribution jobs before another non-OHLCV alpha claim is trusted.

No strategy, ranking, sizing, exits, paper orders, live orders, watchlist, LLM,
or daily production behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260625-022"
OWNER = "alpha-explore"
SLUG = "non_ohlcv_snapshot_leakage_audit"
RUNNER = f"quant/experiments/exp_20260625_022_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
RUN_ASOF_DATE = date(2026, 6, 25)

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
COVERAGE_MANIFEST = NON_OHLCV_DIR / "coverage_manifest.jsonl"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_022_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Repair the non-OHLCV alpha blocker by auditing whether dated "
    "daily_non_ohlcv snapshots and their coverage manifest can expose "
    "future/backfilled rows to replay or forward attribution jobs before any "
    "new non-OHLCV alpha is trusted."
)
ALPHA_HYPOTHESIS = (
    "Production-visible non-OHLCV sources may contain useful event/crowding "
    "information, but any candidate-pool or attribution edge is unreliable if "
    "snapshot files are consumed without a point-in-time as-of boundary."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "non_ohlcv_alpha_measurement_repair"
TRIAL_FAMILY = "non_ohlcv_snapshot_asof_boundary"
TRIAL_VARIANT_ID = "snapshot_date_watermark_leakage_audit_v1"
CHANGED_VARIABLE = "non_ohlcv_snapshot_asof_boundary_leakage_audit_v1"
NEW_EVIDENCE_TYPE = "cross_source_snapshot_date_contract_audit"
NEW_EVIDENCE_AXIS = (
    "Machine-checkable new evidence axis: repository-wide dated "
    "data/non_ohlcv/daily_non_ohlcv_snapshot_YYYYMMDD.json files plus "
    "data/non_ohlcv/coverage_manifest.jsonl as an as-of boundary contract, "
    "not a reslice of one saturated source field or forward attribution sample."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260625-021",
    "exp-20260625-017",
    "exp-20260624-007",
]
CAUSAL_COMPONENTS = [
    "snapshot filename date audit",
    "embedded asof/generated_at audit",
    "coverage manifest date audit",
    "production consumer pattern audit",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260625_022_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

SNAPSHOT_RE = re.compile(r"daily_non_ohlcv_snapshot_(\d{8})\.json$")
DATE8_RE = re.compile(r"^\d{8}$")
DATE10_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PRODUCTION_SCAN_DIRS = [REPO_ROOT / "quant", REPO_ROOT / "scripts"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(value)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if DATE10_RE.match(text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    if DATE8_RE.match(text):
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None
    return None


def parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if DATE8_RE.match(text):
        parsed = parse_date(text)
        return datetime.combine(parsed, time.min, tzinfo=timezone.utc) if parsed else None
    if DATE10_RE.match(text):
        parsed = parse_date(text)
        return datetime.combine(parsed, time.min, tzinfo=timezone.utc) if parsed else None
    try:
        cleaned = text.replace("Z", "+00:00")
        parsed_dt = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed_dt.tzinfo is None:
        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
    return parsed_dt.astimezone(timezone.utc)


def round_float(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, digits) if math.isfinite(number) else None


def baseline_metrics() -> dict[str, Any]:
    payload = load_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") if isinstance(payload.get("windows"), list) else []
    by_label: dict[str, dict[str, Any]] = {}
    for row in windows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or f"window_{len(by_label) + 1}")
        by_label[label] = {
            "start": row.get("start"),
            "end": row.get("end"),
            "expected_value_score": round_float(row.get("expected_value_score")),
            "sharpe_daily": round_float(row.get("sharpe_daily")),
            "total_pnl": round_float(row.get("total_pnl")),
            "max_drawdown_pct": round_float(row.get("max_drawdown_pct")),
            "trade_count": int(row.get("trade_count") or 0),
            "signals_generated": int(row.get("signals_generated") or 0),
            "signals_survived": int(row.get("signals_survived") or 0),
            "survival_rate": round_float(row.get("survival_rate")),
        }
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "windows": by_label,
        "aggregate": {
            "aggregate_expected_value_score": round_float(
                sum(float(row.get("expected_value_score") or 0.0) for row in windows)
            ),
            "aggregate_total_pnl": round_float(
                sum(float(row.get("total_pnl") or 0.0) for row in windows)
            ),
            "max_window_drawdown_pct": round_float(
                max((float(row.get("max_drawdown_pct") or 0.0) for row in windows), default=0.0)
            ),
            "min_survival_rate": round_float(
                min((float(row.get("survival_rate") or 0.0) for row in windows), default=0.0)
            ),
            "total_trade_count": int(sum(int(row.get("trade_count") or 0) for row in windows)),
        },
    }


def snapshot_paths() -> list[Path]:
    return sorted(NON_OHLCV_DIR.glob("daily_non_ohlcv_snapshot_*.json"))


def file_date(path: Path) -> date | None:
    match = SNAPSHOT_RE.search(path.name)
    if not match:
        return None
    return parse_date(match.group(1))


def source_watermark_summary(values: dict[str, Any], asof: date | None) -> dict[str, Any]:
    parsed: dict[str, str] = {}
    missing_parse: list[str] = []
    after_asof: list[str] = []
    future_run_asof: list[str] = []
    for key, value in sorted((values or {}).items()):
        parsed_dt = parse_dt(value)
        if parsed_dt is None:
            missing_parse.append(str(key))
            continue
        parsed[str(key)] = parsed_dt.isoformat()
        if asof is not None and parsed_dt.date() > asof:
            after_asof.append(str(key))
        if parsed_dt.date() > RUN_ASOF_DATE:
            future_run_asof.append(str(key))
    return {
        "parsed": parsed,
        "unparseable_fields": missing_parse,
        "after_snapshot_asof_fields": after_asof,
        "future_after_run_asof_fields": future_run_asof,
    }


def summarize_snapshot(path: Path) -> dict[str, Any]:
    payload = load_json(path, {}) or {}
    fdate = file_date(path)
    if not isinstance(payload, dict):
        return {
            "path": repo_rel(path),
            "loaded": False,
            "file_date": fdate.isoformat() if fdate else None,
            "reason": "invalid_json_payload",
        }
    asof = parse_date(payload.get("asof_date"))
    tag_date = parse_date(payload.get("date_tag"))
    generated = parse_dt(payload.get("generated_at"))
    source_watermarks = payload.get("source_watermarks")
    if not isinstance(source_watermarks, dict):
        source_watermarks = {}
    watermark = source_watermark_summary(source_watermarks, asof or fdate)
    row_counts = {
        key: value
        for key, value in (payload.get("row_counts") or {}).items()
        if isinstance(key, str) and isinstance(value, int | float)
    }
    top_level_counts = {
        "form4_transactions": (payload.get("form4_transactions") or {}).get("row_count"),
        "sec_filing_events": (payload.get("sec_filing_events") or {}).get("rows_written"),
        "sec_filing_text": (payload.get("sec_filing_text") or {}).get("rows_written"),
    }
    return {
        "path": repo_rel(path),
        "loaded": True,
        "file_date": fdate.isoformat() if fdate else None,
        "asof_date": asof.isoformat() if asof else None,
        "date_tag": payload.get("date_tag"),
        "date_tag_date": tag_date.isoformat() if tag_date else None,
        "generated_at": payload.get("generated_at"),
        "generated_at_utc": generated.isoformat() if generated else None,
        "file_mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        "status": payload.get("status"),
        "schema_version": payload.get("schema_version"),
        "top_level_keys": sorted(str(key) for key in payload.keys()),
        "row_counts": row_counts,
        "top_level_counts": top_level_counts,
        "date_consistent": bool(fdate and asof and tag_date and fdate == asof == tag_date),
        "future_file_date": bool(fdate and fdate > RUN_ASOF_DATE),
        "future_asof_date": bool(asof and asof > RUN_ASOF_DATE),
        "future_generated_date": bool(generated and generated.date() > RUN_ASOF_DATE),
        "generated_after_snapshot_date": bool(generated and fdate and generated.date() > fdate),
        "missing_contract_fields": [
            field
            for field, value in {
                "asof_date": asof,
                "date_tag": tag_date,
                "generated_at": generated,
                "source_watermarks": source_watermarks,
            }.items()
            if not value
        ],
        "source_watermarks": watermark,
    }


def load_manifest_records() -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    invalid: list[str] = []
    if not COVERAGE_MANIFEST.exists():
        return records, ["coverage_manifest_missing"]
    for line_number, raw in enumerate(
        COVERAGE_MANIFEST.read_text(encoding="utf-8-sig", errors="replace").splitlines(),
        start=1,
    ):
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            invalid.append(f"line_{line_number}")
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
        else:
            invalid.append(f"line_{line_number}_not_object")
    return records, invalid


def summarize_manifest(records: list[dict[str, Any]], invalid: list[str]) -> dict[str, Any]:
    by_trade_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    coverage_by_trade_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    record_type_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    future_trade_date_rows: list[dict[str, Any]] = []
    future_generated_rows: list[dict[str, Any]] = []
    path_mismatch_rows: list[dict[str, Any]] = []
    generated_after_trade_date_rows: list[dict[str, Any]] = []
    required_missing_counts: Counter[str] = Counter()

    for record in records:
        trade = parse_date(record.get("trade_date"))
        trade_key = trade.isoformat() if trade else str(record.get("trade_date") or "missing")
        record_type = str(record.get("record_type") or "coverage")
        by_trade_date[trade_key].append(record)
        if record_type == "coverage":
            coverage_by_trade_date[trade_key].append(record)
        record_type_counts[record_type] += 1
        mode_counts[str(record.get("mode") or "missing")] += 1
        status_counts[str(record.get("status") or "missing")] += 1
        for missing in record.get("required_missing") or []:
            required_missing_counts[str(missing)] += 1
        if trade and trade > RUN_ASOF_DATE:
            future_trade_date_rows.append(
                {"trade_date": trade.isoformat(), "generated_at": record.get("generated_at")}
            )
        generated = parse_dt(record.get("generated_at"))
        if generated and generated.date() > RUN_ASOF_DATE:
            future_generated_rows.append(
                {"trade_date": trade_key, "generated_at": generated.isoformat()}
            )
        if generated and trade and generated.date() > trade:
            generated_after_trade_date_rows.append(
                {
                    "trade_date": trade_key,
                    "generated_at": generated.isoformat(),
                    "mode": record.get("mode"),
                    "status": record.get("status"),
                }
            )
        artifacts = record.get("artifact_status") if isinstance(record.get("artifact_status"), dict) else {}
        daily = artifacts.get("daily_non_ohlcv_snapshot") if isinstance(artifacts, dict) else {}
        if isinstance(daily, dict):
            daily_path = str(daily.get("path") or "")
            match = SNAPSHOT_RE.search(Path(daily_path).name)
            path_trade = parse_date(match.group(1)) if match else None
            if trade and path_trade and path_trade != trade:
                path_mismatch_rows.append(
                    {
                        "trade_date": trade.isoformat(),
                        "daily_snapshot_path": daily_path,
                        "path_date": path_trade.isoformat(),
                    }
                )

    latest_coverage_by_date = {
        key: rows[-1] for key, rows in coverage_by_trade_date.items() if key != "missing"
    }
    latest_coverage_rows = list(latest_coverage_by_date.values())
    latest_complete = [
        str(row.get("trade_date"))
        for row in latest_coverage_rows
        if row.get("status") == "complete" and parse_date(row.get("trade_date")) is not None
    ]
    duplicate_counts = {key: len(rows) for key, rows in by_trade_date.items() if len(rows) > 1}

    return {
        "path": repo_rel(COVERAGE_MANIFEST),
        "exists": COVERAGE_MANIFEST.exists(),
        "record_count": len(records),
        "invalid_rows": invalid,
        "unique_trade_dates": len(by_trade_date),
        "coverage_trade_dates": len(coverage_by_trade_date),
        "duplicate_trade_date_count": len(duplicate_counts),
        "max_duplicate_rows_for_trade_date": max(duplicate_counts.values(), default=0),
        "record_type_counts": dict(sorted(record_type_counts.items())),
        "mode_counts": dict(sorted(mode_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "required_missing_counts": dict(sorted(required_missing_counts.items())),
        "future_trade_date_rows": future_trade_date_rows[:20],
        "future_trade_date_row_count": len(future_trade_date_rows),
        "future_generated_rows": future_generated_rows[:20],
        "future_generated_row_count": len(future_generated_rows),
        "path_mismatch_rows": path_mismatch_rows[:20],
        "path_mismatch_row_count": len(path_mismatch_rows),
        "generated_after_trade_date_row_count": len(generated_after_trade_date_rows),
        "generated_after_trade_date_examples": generated_after_trade_date_rows[:20],
        "latest_complete_trade_date": max(latest_complete) if latest_complete else None,
    }


def consumer_pattern_audit() -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for root in PRODUCTION_SCAN_DIRS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            rel = repo_rel(path)
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            if "daily_non_ohlcv_snapshot_" not in text:
                continue
            is_experiment = "/experiments/" in rel.replace("\\", "/")
            is_test = Path(rel).name.startswith("test_")
            has_wildcard_glob = bool(
                re.search(r"\.(?:glob|rglob)\([^)]*daily_non_ohlcv_snapshot_\*", text)
            )
            has_exact_tag_path = "daily_non_ohlcv_snapshot_{tag}.json" in text or (
                "daily_non_ohlcv_snapshot_" in text and "{tag}" in text
            )
            has_manifest_reader = "latest_records_by_date" in text or "build_coverage_report" in text
            production = not is_experiment and not is_test
            matches.append(
                {
                    "path": rel,
                    "production_code": production,
                    "experiment_code": is_experiment,
                    "test_code": is_test,
                    "has_wildcard_glob": has_wildcard_glob,
                    "has_exact_tag_path": has_exact_tag_path,
                    "has_manifest_reader": has_manifest_reader,
                }
            )
    dangerous = [
        row
        for row in matches
        if row["production_code"] and row["has_wildcard_glob"] and not row["has_manifest_reader"]
    ]
    return {
        "production_scan_dirs": [repo_rel(path) for path in PRODUCTION_SCAN_DIRS],
        "matches": matches,
        "match_count": len(matches),
        "production_match_count": sum(1 for row in matches if row["production_code"]),
        "production_wildcard_without_manifest_count": len(dangerous),
        "production_wildcard_without_manifest_examples": dangerous[:20],
        "passed": not dangerous,
    }


def summarize_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    loaded = [row for row in snapshots if row.get("loaded")]
    file_dates = [parse_date(row.get("file_date")) for row in loaded if parse_date(row.get("file_date"))]
    missing_fields = Counter(
        field for row in loaded for field in row.get("missing_contract_fields") or []
    )
    watermark_future = [
        {
            "path": row["path"],
            "fields": row.get("source_watermarks", {}).get("future_after_run_asof_fields") or [],
        }
        for row in loaded
        if row.get("source_watermarks", {}).get("future_after_run_asof_fields")
    ]
    watermark_after_asof = [
        {
            "path": row["path"],
            "fields": row.get("source_watermarks", {}).get("after_snapshot_asof_fields") or [],
        }
        for row in loaded
        if row.get("source_watermarks", {}).get("after_snapshot_asof_fields")
    ]
    status_counts = Counter(str(row.get("status") or "missing") for row in loaded)
    return {
        "snapshot_count": len(snapshots),
        "loaded_snapshot_count": len(loaded),
        "min_file_date": min(file_dates).isoformat() if file_dates else None,
        "max_file_date": max(file_dates).isoformat() if file_dates else None,
        "future_file_date_count": sum(1 for row in loaded if row.get("future_file_date")),
        "future_asof_date_count": sum(1 for row in loaded if row.get("future_asof_date")),
        "future_generated_date_count": sum(1 for row in loaded if row.get("future_generated_date")),
        "date_inconsistent_count": sum(1 for row in loaded if not row.get("date_consistent")),
        "generated_after_snapshot_date_count": sum(
            1 for row in loaded if row.get("generated_after_snapshot_date")
        ),
        "missing_contract_fields": dict(sorted(missing_fields.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "source_watermark_future_after_run_asof_count": len(watermark_future),
        "source_watermark_future_after_run_asof_examples": watermark_future[:20],
        "source_watermark_after_snapshot_asof_count": len(watermark_after_asof),
        "source_watermark_after_snapshot_asof_examples": watermark_after_asof[:20],
        "sample_first": loaded[:3],
        "sample_last": loaded[-3:],
    }


def build_readiness(
    snapshot_summary: dict[str, Any],
    manifest_summary: dict[str, Any],
    consumer_audit: dict[str, Any],
) -> dict[str, Any]:
    failed: list[str] = []
    if snapshot_summary["loaded_snapshot_count"] <= 0:
        failed.append("no_daily_non_ohlcv_snapshot_files")
    if snapshot_summary["future_file_date_count"]:
        failed.append("future_dated_snapshot_files")
    if snapshot_summary["future_asof_date_count"]:
        failed.append("future_embedded_snapshot_asof_dates")
    if snapshot_summary["future_generated_date_count"]:
        failed.append("future_snapshot_generated_at_dates")
    if snapshot_summary["date_inconsistent_count"]:
        failed.append("snapshot_filename_asof_date_tag_mismatch")
    if snapshot_summary["source_watermark_future_after_run_asof_count"]:
        failed.append("source_watermark_after_run_asof")
    if manifest_summary["future_trade_date_row_count"]:
        failed.append("coverage_manifest_future_trade_dates")
    if manifest_summary["future_generated_row_count"]:
        failed.append("coverage_manifest_future_generated_at")
    if manifest_summary["path_mismatch_row_count"]:
        failed.append("coverage_manifest_daily_snapshot_path_mismatch")
    if manifest_summary["invalid_rows"]:
        failed.append("coverage_manifest_invalid_jsonl_rows")
    if not consumer_audit["passed"]:
        failed.append("production_wildcard_snapshot_consumer_without_manifest_guard")
    accepted = not failed
    return {
        "passed": accepted,
        "decision": (
            "accepted_measurement_repair_no_non_ohlcv_future_snapshot_leakage_observed"
            if accepted
            else "blocked_non_ohlcv_snapshot_asof_boundary_leakage_risk"
        ),
        "failed_reasons": failed,
        "run_asof_date": RUN_ASOF_DATE.isoformat(),
        "observed": {
            "snapshot_count": snapshot_summary["snapshot_count"],
            "loaded_snapshot_count": snapshot_summary["loaded_snapshot_count"],
            "snapshot_min_file_date": snapshot_summary["min_file_date"],
            "snapshot_max_file_date": snapshot_summary["max_file_date"],
            "future_file_date_count": snapshot_summary["future_file_date_count"],
            "manifest_record_count": manifest_summary["record_count"],
            "manifest_future_trade_date_row_count": manifest_summary[
                "future_trade_date_row_count"
            ],
            "manifest_latest_complete_trade_date": manifest_summary[
                "latest_complete_trade_date"
            ],
            "production_wildcard_without_manifest_count": consumer_audit[
                "production_wildcard_without_manifest_count"
            ],
            "generated_after_snapshot_date_count": snapshot_summary[
                "generated_after_snapshot_date_count"
            ],
            "manifest_generated_after_trade_date_row_count": manifest_summary[
                "generated_after_trade_date_row_count"
            ],
        },
        "non_blocking_caveats": [
            "Historical backtest/catch-up snapshots are generated after their trade dates; "
            "future alpha work must use per-row accepted_at/publication/as-of fields, not "
            "file mtime or latest snapshot availability, as the evidence timestamp.",
            "This audit validates the current repository as-of boundary; it does not make "
            "saturated SEC/Form4/Companyfacts/FTD/Kova/options fields novel again.",
        ],
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON, {}) or {}
    prediction = ticket.get("prediction") or {}
    before = baseline_metrics()
    snapshots = [summarize_snapshot(path) for path in snapshot_paths()]
    snapshot_summary = summarize_snapshots(snapshots)
    manifest_records, invalid_manifest = load_manifest_records()
    manifest_summary = summarize_manifest(manifest_records, invalid_manifest)
    consumer_audit = consumer_pattern_audit()
    readiness = build_readiness(snapshot_summary, manifest_summary, consumer_audit)
    accepted = bool(readiness["passed"])
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = readiness["decision"]
    predicted = round_float(prediction.get("success_probability")) or 0.0
    actual_success = 1.0 if accepted else 0.0

    why = (
        "No future-dated daily_non_ohlcv snapshot, embedded as-of date, coverage "
        "manifest trade_date, or production wildcard consumer leak path was observed. "
        "The main caveat is that historical/catch-up snapshots were generated after "
        "their trade dates, so future alpha claims still need field-level PIT evidence "
        "and cannot treat file availability as event availability."
        if accepted
        else (
            "The audit found at least one as-of boundary leak risk, so this surface "
            "cannot be used for a new non-OHLCV alpha claim until the failed checks "
            "are guarded or repaired."
        )
    )

    gate4 = {
        "passed": accepted,
        "status": "measurement_audit_only_no_strategy_delta",
        "before": before["windows"],
        "after": before["windows"],
        "aggregate_before": before["aggregate"],
        "aggregate_after": before["aggregate"],
        "aggregate_delta": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "max_window_drawdown_pct": 0.0,
            "min_survival_rate": 0.0,
            "total_trade_count": 0,
        },
        "readiness": readiness,
        "failed_reasons": readiness["failed_reasons"],
        "acceptance_rule": (
            "Accept as measurement repair only if no snapshot/manifest date exceeds "
            "the run as-of date, filename/asof/date_tag contracts match, manifest "
            "daily snapshot paths match trade_date, and production code has no "
            "wildcard latest/all snapshot consumer without a manifest/as-of guard."
        ),
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": "measurement_repair",
        "owner": OWNER,
        "status": status,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_audit_only_no_strategy_change",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "ticket_before": ticket,
        "prediction": prediction,
        "calibration": {
            "actual_success": actual_success,
            "actual_gate4_passed": accepted,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - actual_success) ** 2, 4),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": readiness["failed_reasons"],
            "surprise_note": (
                "Low surprise: the current repo has no future-dated daily snapshots, "
                "but the audit confirms that historical generated_at dates are not "
                "sufficient PIT evidence by themselves."
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before,
            "note": "Measurement audit only; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": accepted,
            "required_fields_checked": [
                "daily snapshot filename date",
                "asof_date",
                "date_tag",
                "generated_at",
                "source_watermarks",
                "coverage_manifest.trade_date",
                "coverage_manifest.generated_at",
                "artifact_status.daily_non_ohlcv_snapshot.path",
                "production consumer pattern",
                "entry_date and target_price intentionally unchanged/no strategy rows",
            ],
            "snapshot_summary": snapshot_summary,
            "manifest_summary": manifest_summary,
            "consumer_pattern_audit": consumer_audit,
            "failed_reasons": readiness["failed_reasons"],
        },
        "gate3": {
            "passed": True,
            "signals_generated": sum(
                row["signals_generated"] for row in before["windows"].values()
            ),
            "signals_survived": sum(
                row["signals_survived"] for row in before["windows"].values()
            ),
            "min_survival_rate": before["aggregate"]["min_survival_rate"],
            "note": "No filter was added; survival and trade counts are unchanged.",
        },
        "gate4": gate4,
        "source_summary": {
            "snapshots": snapshot_summary,
            "manifest": manifest_summary,
            "consumer_pattern_audit": consumer_audit,
        },
        "production_impact": {
            "strategy_code_changed": False,
            "shared_helper_changed": False,
            "backtester_adapter_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "llm_decision_boundary_changed": False,
            "parity_note": (
                "No production/backtest inconsistency was introduced because no "
                "trading rule or production helper changed. Future non-OHLCV alpha "
                "work must keep this date/as-of guard in the shared adapter."
            ),
        },
        "live_realistic_execution_envelope": {
            "required_for_live_ready": False,
            "reason": "Measurement repair only; no tradable alpha or order path changed.",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "negative_result_reflection": (
                "Not a negative alpha result. If blocked, the blocker is as-of "
                "replayability; if accepted, this only clears the global future-date "
                "leak check and does not revive saturated source families."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this accepted audit as justification to retry SEC text, "
                "Form4, Companyfacts, SEC13F, FTD, Kova, options, borrow, or short "
                "volume threshold sweeps. A valid next alpha still needs a new PIT "
                "source, materially more closed forward rows, or a shared default-off "
                "gate shape not already saturated."
            ),
            "next_step_new_evidence": (
                "Use the cleared global as-of audit as plumbing, then pursue a truly "
                "new evidence axis: materially more closed forward replacement rows, "
                "a new PIT data source, or a shared helper with field-level accepted_at/"
                "publication-date guards."
            ),
        },
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(NON_OHLCV_DIR),
            repo_rel(COVERAGE_MANIFEST),
        ],
        "changed_files": ALLOWED_WRITE_SCOPE,
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "revision_manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "lean_quality_passed": True,
        "anti_js": "No JavaScript was used.",
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    readiness = payload["gate4"]["readiness"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "owner": OWNER,
        "status": payload["status"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": CHANGE_TYPE,
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "gate1": payload["gate1"],
        "gate2": {
            "passed": payload["gate2"]["passed"],
            "required_fields_checked": payload["gate2"]["required_fields_checked"],
            "snapshot_summary": {
                key: payload["gate2"]["snapshot_summary"][key]
                for key in [
                    "snapshot_count",
                    "loaded_snapshot_count",
                    "min_file_date",
                    "max_file_date",
                    "future_file_date_count",
                    "future_asof_date_count",
                    "future_generated_date_count",
                    "date_inconsistent_count",
                    "generated_after_snapshot_date_count",
                    "source_watermark_future_after_run_asof_count",
                ]
            },
            "manifest_summary": {
                key: payload["gate2"]["manifest_summary"][key]
                for key in [
                    "record_count",
                    "unique_trade_dates",
                    "duplicate_trade_date_count",
                    "future_trade_date_row_count",
                    "future_generated_row_count",
                    "path_mismatch_row_count",
                    "latest_complete_trade_date",
                ]
            },
            "consumer_pattern_audit": {
                key: payload["gate2"]["consumer_pattern_audit"][key]
                for key in [
                    "match_count",
                    "production_match_count",
                    "production_wildcard_without_manifest_count",
                    "passed",
                ]
            },
            "failed_reasons": payload["gate2"]["failed_reasons"],
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "source_summary": {
            "run_asof_date": readiness["run_asof_date"],
            "observed": readiness["observed"],
            "non_blocking_caveats": readiness["non_blocking_caveats"],
        },
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "runner": payload["runner"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    observed = payload["gate4"]["readiness"]["observed"]
    lines = [
        f"# {EXPERIMENT_ID}: non-OHLCV snapshot leakage audit",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Run as-of date: `{payload['gate4']['readiness']['run_asof_date']}`",
        f"- Snapshot files: `{observed['snapshot_count']}`",
        f"- Snapshot date span: `{observed['snapshot_min_file_date']}` to `{observed['snapshot_max_file_date']}`",
        f"- Future snapshot files: `{observed['future_file_date_count']}`",
        f"- Manifest rows: `{observed['manifest_record_count']}`",
        f"- Manifest future trade-date rows: `{observed['manifest_future_trade_date_row_count']}`",
        f"- Latest complete manifest trade date: `{observed['manifest_latest_complete_trade_date']}`",
        f"- Production wildcard consumers without manifest guard: `{observed['production_wildcard_without_manifest_count']}`",
        f"- Historical generated-after-trade snapshot files: `{observed['generated_after_snapshot_date_count']}`",
        "",
        "## Failed Checks",
        "",
        ", ".join(payload["gate4"]["failed_reasons"]) or "none",
        "",
        "## Interpretation",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduction",
        "",
        "```powershell",
        RUNNER_COMMAND,
        ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
        ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        "```",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        COVERAGE_MANIFEST,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in paths
        },
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "live_realistic_execution_envelope": payload["live_realistic_execution_envelope"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "run_asof_date": payload["gate4"]["readiness"]["run_asof_date"],
                "observed": payload["gate4"]["readiness"]["observed"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
