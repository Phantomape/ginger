"""Coverage manifest helpers for replayable non-OHLCV data.

The manifest is append-only. Readers use the latest row per trade_date so a
failed or partial run can be repaired later without rewriting history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = REPO_ROOT / "data"
DEFAULT_NON_OHLCV_DIR = DEFAULT_DATA_ROOT / "non_ohlcv"
MANIFEST_FILENAME = "coverage_manifest.jsonl"
VALID_RECORD_STATUSES = {"complete", "partial", "failed"}


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    path: Path
    kind: str
    required: bool = True


def parse_trade_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def date_key(value: str | date | datetime) -> str:
    return parse_trade_date(value).strftime("%Y%m%d")


def iso_date(value: str | date | datetime) -> str:
    return parse_trade_date(value).isoformat()


def iter_business_days(start: str | date | datetime, end: str | date | datetime) -> list[date]:
    current = parse_trade_date(start)
    last = parse_trade_date(end)
    days: list[date] = []
    while current <= last:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def next_business_day(value: str | date | datetime) -> date:
    current = parse_trade_date(value) + timedelta(days=1)
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current


def previous_business_day(value: str | date | datetime) -> date:
    current = parse_trade_date(value) - timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def resolve_data_root(data_root: str | Path | None = None) -> Path:
    return Path(data_root) if data_root is not None else DEFAULT_DATA_ROOT


def resolve_non_ohlcv_dir(
    non_ohlcv_dir: str | Path | None = None,
    *,
    data_root: str | Path | None = None,
) -> Path:
    if non_ohlcv_dir is not None:
        return Path(non_ohlcv_dir)
    return resolve_data_root(data_root) / "non_ohlcv"


def manifest_path(
    non_ohlcv_dir: str | Path | None = None,
    *,
    data_root: str | Path | None = None,
) -> Path:
    return resolve_non_ohlcv_dir(non_ohlcv_dir, data_root=data_root) / MANIFEST_FILENAME


def artifact_specs(
    trade_date: str | date | datetime,
    *,
    data_root: str | Path | None = None,
    non_ohlcv_dir: str | Path | None = None,
    include_options: bool = False,
    include_filing_features: bool = True,
) -> list[ArtifactSpec]:
    root = resolve_data_root(data_root)
    non_root = resolve_non_ohlcv_dir(non_ohlcv_dir, data_root=root)
    tag = date_key(trade_date)
    specs = [
        ArtifactSpec("earnings_snapshot", root / f"earnings_snapshot_{tag}.json", "json"),
        ArtifactSpec("daily_non_ohlcv_snapshot", non_root / f"daily_non_ohlcv_snapshot_{tag}.json", "json"),
        ArtifactSpec("sec_filing_events", non_root / f"sec_filing_events_{tag}.jsonl", "jsonl"),
        ArtifactSpec("sec_filing_text", non_root / f"sec_filing_text_{tag}.jsonl", "jsonl"),
        ArtifactSpec("form4_transactions", non_root / f"form4_transactions_{tag}.jsonl", "jsonl"),
        ArtifactSpec("event_snapshot", root / f"event_snapshot_{tag}.json", "json"),
    ]
    if include_filing_features:
        specs.append(
            ArtifactSpec(
                "sec_filing_features",
                non_root / f"sec_filing_features_{tag}.jsonl",
                "jsonl",
                required=False,
            )
        )
    if include_options:
        specs.append(
            ArtifactSpec(
                "options_onclickmedia_chain",
                non_root / f"options_onclickmedia_chain_{tag}.jsonl",
                "jsonl",
                required=False,
            )
        )
    return specs


def append_manifest_record(
    record: dict[str, Any],
    *,
    non_ohlcv_dir: str | Path | None = None,
    data_root: str | Path | None = None,
) -> Path:
    status = record.get("status")
    if status not in VALID_RECORD_STATUSES:
        raise ValueError(f"invalid non-OHLCV coverage status: {status!r}")
    path = manifest_path(non_ohlcv_dir, data_root=data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def load_manifest_records(
    *,
    non_ohlcv_dir: str | Path | None = None,
    data_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    path = manifest_path(non_ohlcv_dir, data_root=data_root)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def latest_records_by_date(
    *,
    non_ohlcv_dir: str | Path | None = None,
    data_root: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in load_manifest_records(non_ohlcv_dir=non_ohlcv_dir, data_root=data_root):
        trade_date = record.get("trade_date")
        if trade_date:
            latest[str(trade_date)] = record
    return latest


def latest_complete_trade_date(
    *,
    non_ohlcv_dir: str | Path | None = None,
    data_root: str | Path | None = None,
) -> date | None:
    complete_dates = [
        parse_trade_date(trade_date)
        for trade_date, record in latest_records_by_date(
            non_ohlcv_dir=non_ohlcv_dir,
            data_root=data_root,
        ).items()
        if record.get("status") == "complete"
    ]
    return max(complete_dates) if complete_dates else None


def is_coverage_complete(
    trade_date: str | date | datetime,
    *,
    data_root: str | Path | None = None,
    non_ohlcv_dir: str | Path | None = None,
    include_options: bool = False,
    include_filing_features: bool = True,
) -> bool:
    record = build_coverage_record(
        trade_date,
        mode="audit",
        data_root=data_root,
        non_ohlcv_dir=non_ohlcv_dir,
        include_options=include_options,
        include_filing_features=include_filing_features,
    )
    return record["status"] == "complete"


def build_coverage_record(
    trade_date: str | date | datetime,
    *,
    mode: str,
    data_root: str | Path | None = None,
    non_ohlcv_dir: str | Path | None = None,
    include_options: bool = False,
    include_filing_features: bool = True,
    errors: list[dict[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    trade_date_iso = iso_date(trade_date)
    artifacts: dict[str, Any] = {}
    source_watermarks: dict[str, Any] = {}
    required_missing: list[str] = []
    invalid_required: list[str] = []
    sec_rows_missing_accepted = 0
    sec_rows_missing_usable = 0

    for spec in artifact_specs(
        trade_date,
        data_root=data_root,
        non_ohlcv_dir=non_ohlcv_dir,
        include_options=include_options,
        include_filing_features=include_filing_features,
    ):
        artifact = _inspect_artifact(spec)
        artifacts[spec.name] = artifact
        if artifact.get("source_watermark") is not None:
            source_watermarks[spec.name] = artifact["source_watermark"]
        sec_rows_missing_accepted += artifact.get("sec_rows_missing_accepted_at", 0) or 0
        sec_rows_missing_usable += artifact.get("sec_rows_missing_usable_trade_date", 0) or 0
        if spec.required and artifact["status"] == "missing":
            required_missing.append(spec.name)
        if spec.required and artifact["status"] in {"invalid", "failed"}:
            invalid_required.append(spec.name)

    errors = errors or []
    if required_missing or invalid_required:
        status = "partial"
    elif errors:
        status = "partial"
    else:
        status = "complete"

    if invalid_required and len(invalid_required) == len([s for s in artifact_specs(trade_date) if s.required]):
        status = "failed"

    if sec_rows_missing_accepted or sec_rows_missing_usable:
        pit_overall = "biased"
        status = "partial"
    elif status == "complete":
        pit_overall = "sec_pit_safe_with_earnings_proxy"
    else:
        pit_overall = "incomplete"

    return {
        "schema_version": 1,
        "trade_date": trade_date_iso,
        "date_key": date_key(trade_date),
        "mode": mode,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "artifact_status": artifacts,
        "row_counts": {
            name: artifact.get("row_count")
            for name, artifact in artifacts.items()
        },
        "source_watermarks": source_watermarks,
        "pit_status": {
            "overall": pit_overall,
            "sec_rows_missing_accepted_at": sec_rows_missing_accepted,
            "sec_rows_missing_usable_trade_date": sec_rows_missing_usable,
            "earnings_snapshot_caveat": (
                "Daily production snapshots are replayable; historical yfinance backfills "
                "remain PIT-ish and must not be treated as vendor consensus truth."
            ),
        },
        "errors": errors,
        "required_missing": required_missing,
        "invalid_required": invalid_required,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": mode == "backtest",
            "run_adapter_changed": mode in {"daily", "catchup"},
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
    }


def build_coverage_report(
    start: str | date | datetime,
    end: str | date | datetime,
    *,
    data_root: str | Path | None = None,
    non_ohlcv_dir: str | Path | None = None,
    include_options: bool = False,
    include_filing_features: bool = True,
) -> dict[str, Any]:
    records = [
        build_coverage_record(
            day,
            mode="backtest_audit",
            data_root=data_root,
            non_ohlcv_dir=non_ohlcv_dir,
            include_options=include_options,
            include_filing_features=include_filing_features,
        )
        for day in iter_business_days(start, end)
    ]
    total = len(records)
    complete = sum(1 for record in records if record["status"] == "complete")
    partial = sum(1 for record in records if record["status"] == "partial")
    failed = sum(1 for record in records if record["status"] == "failed")
    missing_by_artifact: dict[str, int] = {}
    for record in records:
        for artifact in record.get("required_missing", []):
            missing_by_artifact[artifact] = missing_by_artifact.get(artifact, 0) + 1
    return {
        "schema_version": 1,
        "start": iso_date(start),
        "end": iso_date(end),
        "business_days": total,
        "complete_days": complete,
        "partial_days": partial,
        "failed_days": failed,
        "complete_fraction": round(complete / total, 4) if total else 0.0,
        "missing_by_artifact": dict(sorted(missing_by_artifact.items())),
        "biased_days": sum(
            1 for record in records
            if (record.get("pit_status") or {}).get("overall") == "biased"
        ),
        "records": records,
        "decision": "complete" if complete == total else "biased_or_incomplete",
    }


def write_backtest_coverage_report(
    report: dict[str, Any],
    *,
    non_ohlcv_dir: str | Path | None = None,
    data_root: str | Path | None = None,
) -> Path:
    non_root = resolve_non_ohlcv_dir(non_ohlcv_dir, data_root=data_root)
    start_key = str(report.get("start", "")).replace("-", "")
    end_key = str(report.get("end", "")).replace("-", "")
    path = non_root / f"backtest_coverage_{start_key}_{end_key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _inspect_artifact(spec: ArtifactSpec) -> dict[str, Any]:
    base = {
        "path": _path_text(spec.path),
        "required": spec.required,
        "kind": spec.kind,
    }
    if not spec.path.exists():
        return {**base, "status": "missing", "row_count": 0}
    if spec.kind == "jsonl":
        return {**base, **_inspect_jsonl(spec.path)}
    if spec.kind == "json":
        return {**base, **_inspect_json(spec.path, spec.name)}
    return {**base, "status": "invalid", "row_count": 0, "error": f"unknown kind {spec.kind}"}


def _inspect_json(path: Path, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"status": "invalid", "row_count": 0, "error": str(exc)}
    row_count = _json_row_count(payload, name)
    payload_status = payload.get("status") if isinstance(payload, dict) else None
    status = "failed" if payload_status == "failed" else "present"
    return {
        "status": status,
        "row_count": row_count,
        "payload_status": payload_status,
        "source_watermark": _json_source_watermark(payload),
    }


def _inspect_jsonl(path: Path) -> dict[str, Any]:
    row_count = 0
    invalid_count = 0
    max_watermark = None
    sec_missing_accepted = 0
    sec_missing_usable = 0
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            invalid_count += 1
            continue
        row_count += 1
        watermark = _row_watermark(row)
        if watermark and (max_watermark is None or watermark > max_watermark):
            max_watermark = watermark
        if _looks_like_sec_row(row):
            if not (row.get("accepted_at") or row.get("accepted_datetime")):
                sec_missing_accepted += 1
            if not row.get("usable_trade_date"):
                sec_missing_usable += 1
    return {
        "status": "invalid" if invalid_count else "present",
        "row_count": row_count,
        "invalid_rows": invalid_count,
        "source_watermark": max_watermark,
        "sec_rows_missing_accepted_at": sec_missing_accepted,
        "sec_rows_missing_usable_trade_date": sec_missing_usable,
    }


def _json_row_count(payload: Any, name: str) -> int:
    if not isinstance(payload, dict):
        return 0
    if name == "earnings_snapshot":
        earnings = payload.get("earnings")
        return len(earnings) if isinstance(earnings, dict) else 0
    if name == "event_snapshot":
        coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
        return int(coverage.get("event_rows_total") or 0)
    if name == "daily_non_ohlcv_snapshot":
        total = 0
        for key in ("sec_filing_events", "sec_filing_text", "form4_transactions", "options_onclickmedia"):
            section = payload.get(key) if isinstance(payload.get(key), dict) else {}
            total += int(section.get("rows_written") or section.get("rows") or 0)
        return total
    return 0


def _json_source_watermark(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("generated_at", "timestamp", "date", "asof_date"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def _row_watermark(row: Any) -> str | None:
    if not isinstance(row, dict):
        return None
    for key in (
        "accepted_at",
        "accepted_datetime",
        "usable_trade_date",
        "transaction_date",
        "filing_date",
        "filed",
        "published_at",
    ):
        value = row.get(key)
        if value:
            return str(value)
    return None


def _looks_like_sec_row(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    form = str(row.get("form_type") or row.get("form") or "").upper()
    return bool(form.startswith(("8-K", "10-Q", "10-K")) or row.get("accession_number"))


def _path_text(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")
