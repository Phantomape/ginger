"""Build a static experiment registry dashboard.

The dashboard is read-only. It indexes experiment records across the registry,
JSONL log, per-experiment tickets/logs, artifacts, and data directories so ID
allocation gaps are visible before the next ticket is created.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from experiment_registry import (
    DEFAULT_REGISTRY,
    REPO_ROOT,
    collect_experiment_id_sources,
    load_registry,
    next_experiment_id,
    normalize_experiment_id,
)


FIELD_KEYS = (
    "experiment_id",
    "experiment_uid",
    "status",
    "decision",
    "lane",
    "owner",
    "hypothesis",
    "change_type",
    "mechanism_family",
    "trial_family",
    "trial_variant_id",
    "changed_variable",
    "single_causal_variable",
    "new_evidence_type",
    "summary",
    "before_metrics",
    "after_metrics",
    "delta_metrics",
    "expected_value_score_delta",
    "total_pnl_delta",
    "timestamp",
    "created_at",
    "claimed_at",
    "completed_at",
    "updated_at",
)

DATASET_FIELDS = (
    "experiment_id",
    "status_group",
    "status",
    "decision",
    "lane",
    "owner",
    "change_type",
    "mechanism_family",
    "trial_family",
    "changed_variable",
    "new_evidence_type",
)

COLLECTION_RULES = (
    {
        "slug": "identity_repair",
        "title": "Identity Repair Queue",
        "description": "Experiments with actionable registry, ticket, log, or artifact drift.",
        "predicate": lambda row: bool(row.get("anomalies")),
    },
    {
        "slug": "archive_identity_notes",
        "title": "Archive Identity Notes",
        "description": "Historical coverage gaps and mirrored files that do not block current coordination.",
        "predicate": lambda row: bool(row.get("identity_notes")),
    },
    {
        "slug": "accepted_stack",
        "title": "Accepted Stack",
        "description": "Accepted experiments and repairs currently visible in the index.",
        "predicate": lambda row: row.get("status_group") == "accepted",
    },
    {
        "slug": "default_off_sleeves",
        "title": "Default-Off Sleeves",
        "description": "Paper, observe-only, or default-off sleeve experiments.",
        "predicate": lambda row: _row_text(row).find("default-off") >= 0
        or _row_text(row).find("paper") >= 0
        or _row_text(row).find("sleeve") >= 0,
    },
    {
        "slug": "measurement_repair",
        "title": "Measurement Repair",
        "description": "Measurement, parity, logging, context, and attribution repairs.",
        "predicate": lambda row: row.get("lane") == "measurement_repair"
        or "measurement" in _row_text(row)
        or "parity" in _row_text(row),
    },
    {
        "slug": "active_queue",
        "title": "Active And Proposed Queue",
        "description": "Open work that may need claiming, closing, or cleanup.",
        "predicate": lambda row: row.get("status_group") in {"active", "proposed"},
    },
)

COORDINATION_SOURCES = {"registry", "ticket", "docs_ticket", "log", "docs_log"}
SOURCE_ALIASES = {
    "docs_ticket": "ticket",
    "docs_log": "log",
}
PATH_PREFIX_ALIASES = (
    ("docs/experiments/tickets/", "experiments/tickets/"),
    ("docs/experiments/logs/", "experiments/logs/"),
)
TICKET_SOURCES = {"ticket"}
LOG_SOURCES = {"log"}
OPEN_STATUS_GROUPS = {"active", "proposed"}
VOLATILE_TICKET_KEYS = {"updated_at"}


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path):
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def status_group(record: dict) -> str:
    text = " ".join(
        str(record.get(key) or "")
        for key in ("status", "decision")
    ).lower()
    if "accepted" in text:
        return "accepted"
    if "rejected" in text or "rolled_back" in text:
        return "rejected"
    if "claimed" in text or "running" in text:
        return "active"
    if "observed" in text:
        return "observed"
    if "proposed" in text:
        return "proposed"
    return "unknown"


def _row_text(row: dict) -> str:
    values = []
    for key in (
        "experiment_id",
        "status",
        "decision",
        "lane",
        "hypothesis",
        "change_type",
        "mechanism_family",
        "trial_family",
        "changed_variable",
        "single_causal_variable",
        "summary",
    ):
        value = row.get(key)
        if value is not None:
            values.append(str(value))
    return " ".join(values).lower()


def default_record(experiment_id: str) -> dict:
    return {
        "experiment_id": experiment_id,
        "sources": [],
        "files": [],
        "anomalies": [],
        "identity_notes": [],
    }


def canonical_source(source: str) -> str:
    return SOURCE_ALIASES.get(source, source)


def source_kind_from_collected_source(source: str) -> str:
    source_kind, _, detail = source.partition(":")
    source_kind = canonical_source(source_kind)
    if detail.startswith("text:") or detail.startswith("ref:"):
        return f"{source_kind}_ref"
    return source_kind


def canonical_identity_path(path: str | None) -> str | None:
    if not path:
        return path
    normalized = str(path).replace("\\", "/")
    for old_prefix, new_prefix in PATH_PREFIX_ALIASES:
        if normalized.startswith(old_prefix):
            return new_prefix + normalized[len(old_prefix):]
    return normalized


def stable_ticket_payload(value):
    if isinstance(value, dict):
        return {
            key: stable_ticket_payload(item)
            for key, item in sorted(value.items())
            if key not in VOLATILE_TICKET_KEYS
        }
    if isinstance(value, list):
        return [stable_ticket_payload(item) for item in value]
    if isinstance(value, str):
        return value.replace("\\", "/")
    return value


def matching_ticket_payloads(ticket_items) -> bool:
    normalized = []
    for _, _, payload in ticket_items:
        if isinstance(payload, dict):
            normalized.append(stable_ticket_payload(payload))
    return bool(normalized) and all(item == normalized[0] for item in normalized[1:])


def should_count_missing_registry_as_anomaly(record: dict, sources: set[str]) -> bool:
    if not (sources & (TICKET_SOURCES | LOG_SOURCES)):
        return False
    return status_group(record) in OPEN_STATUS_GROUPS


def should_count_missing_ticket_as_anomaly(record: dict, sources: set[str]) -> bool:
    if "registry" in sources:
        return True
    if not (sources & LOG_SOURCES):
        return False
    return status_group(record) in OPEN_STATUS_GROUPS


def should_count_jsonl_log_gap_as_anomaly(record: dict, sources: set[str]) -> bool:
    if not (sources & ({"registry"} | TICKET_SOURCES)):
        return False
    return status_group(record) in OPEN_STATUS_GROUPS


def _as_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        try:
            number = float(value.replace(",", "").replace("$", "").replace("%", ""))
            return number if math.isfinite(number) else None
        except ValueError:
            return None
    return None


def clean_for_json(value):
    if isinstance(value, dict):
        return {key: clean_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [clean_for_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _nested_get(mapping, path):
    current = mapping
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def first_number(mapping, paths):
    for path in paths:
        value = _nested_get(mapping, path)
        number = _as_number(value)
        if number is not None:
            return number
    return None


def derive_metrics(row: dict) -> dict:
    ev_delta = first_number(row, [
        ("delta_metrics", "expected_value_score"),
        ("delta_metrics", "expected_value_score_delta"),
        ("delta_metrics", "expected_value_score_delta_sum"),
        ("delta_metrics", "aggregate", "expected_value_score_delta_sum"),
        ("expected_value_score_delta",),
    ])
    pnl_delta = first_number(row, [
        ("delta_metrics", "total_pnl"),
        ("delta_metrics", "total_pnl_delta"),
        ("delta_metrics", "total_pnl_delta_sum"),
        ("delta_metrics", "aggregate", "total_pnl_delta_sum"),
        ("total_pnl_delta",),
    ])
    after_ev = first_number(row, [
        ("after_metrics", "expected_value_score"),
        ("after_metrics", "accepted_core_expected_value_score_sum"),
        ("delta_metrics", "aggregate", "after_expected_value_score_sum"),
    ])
    before_ev = first_number(row, [
        ("before_metrics", "expected_value_score"),
        ("before_metrics", "accepted_core_expected_value_score_sum"),
        ("delta_metrics", "aggregate", "baseline_expected_value_score_sum"),
    ])
    return {
        "expected_value_score_delta": ev_delta,
        "total_pnl_delta": pnl_delta,
        "after_expected_value_score": after_ev,
        "before_expected_value_score": before_ev,
    }


def build_experiment_card(row: dict) -> dict:
    metrics = derive_metrics(row)
    return {
        "id": row.get("experiment_id"),
        "uid": row.get("experiment_uid"),
        "title": row.get("trial_variant_id")
        or row.get("trial_family")
        or row.get("change_type")
        or row.get("experiment_id"),
        "status": row.get("status"),
        "status_group": row.get("status_group"),
        "lane": row.get("lane"),
        "summary": row.get("summary") or row.get("hypothesis"),
        "metadata": {
            "mechanism_family": row.get("mechanism_family"),
            "trial_family": row.get("trial_family"),
            "changed_variable": row.get("changed_variable")
            or row.get("single_causal_variable"),
            "new_evidence_type": row.get("new_evidence_type"),
            "owner": row.get("owner"),
        },
        "metrics": metrics,
        "sources": row.get("sources") or [],
        "anomalies": row.get("anomalies") or [],
        "identity_notes": row.get("identity_notes") or [],
        "files": row.get("files") or [],
    }


def build_leaderboards(rows):
    scored = []
    for row in rows:
        metrics = derive_metrics(row)
        enriched = {
            "experiment_id": row.get("experiment_id"),
            "status_group": row.get("status_group"),
            "trial_family": row.get("trial_family"),
            "mechanism_family": row.get("mechanism_family"),
            "changed_variable": row.get("changed_variable")
            or row.get("single_causal_variable"),
            "summary": row.get("summary") or row.get("hypothesis"),
            **metrics,
        }
        if metrics["expected_value_score_delta"] is not None or metrics["total_pnl_delta"] is not None:
            scored.append(enriched)

    def sort_key(metric):
        return lambda row: (
            row.get(metric) is not None,
            row.get(metric) if row.get(metric) is not None else float("-inf"),
        )

    top_ev = sorted(scored, key=sort_key("expected_value_score_delta"), reverse=True)[:25]
    bottom_ev = sorted(
        [row for row in scored if row.get("expected_value_score_delta") is not None],
        key=lambda row: row["expected_value_score_delta"],
    )[:25]
    top_pnl = sorted(scored, key=sort_key("total_pnl_delta"), reverse=True)[:25]
    family_counter = Counter(
        (row.get("trial_family") or row.get("mechanism_family") or "unknown")
        for row in rows
        if row.get("status_group") == "rejected"
    )
    rejected_families = [
        {"family": family, "count": count}
        for family, count in family_counter.most_common(25)
    ]
    return {
        "top_ev_delta": top_ev,
        "bottom_ev_delta": bottom_ev,
        "top_pnl_delta": top_pnl,
        "rejected_families": rejected_families,
    }


def build_dataset_view(rows):
    columns = []
    for field in DATASET_FIELDS:
        values = [row.get(field) for row in rows]
        present = [str(value) for value in values if value not in (None, "", [], {})]
        counts = Counter(present)
        columns.append({
            "field": field,
            "present": len(present),
            "missing": len(rows) - len(present),
            "unique": len(counts),
            "top_values": [
                {"value": value, "count": count}
                for value, count in counts.most_common(12)
            ],
        })
    return {"columns": columns}


def build_collections(rows):
    collections = []
    for rule in COLLECTION_RULES:
        members = [row.get("experiment_id") for row in rows if rule["predicate"](row)]
        collections.append({
            "slug": rule["slug"],
            "title": rule["title"],
            "description": rule["description"],
            "count": len(members),
            "experiment_ids": members[:200],
        })
    return collections


def merge_record(records: dict, experiment_id: str, payload: dict, source: str, path=None):
    experiment_id = normalize_experiment_id(experiment_id)
    if not experiment_id:
        return
    source = canonical_source(source)
    path = canonical_identity_path(path)
    record = records.setdefault(
        experiment_id,
        default_record(experiment_id),
    )
    if source not in record["sources"]:
        record["sources"].append(source)
    if path and path not in record["files"]:
        record["files"].append(path)
    if isinstance(payload, dict):
        for key in FIELD_KEYS:
            value = payload.get(key)
            if value not in (None, "", [], {}) and record.get(key) in (None, "", [], {}):
                record[key] = value
        result = payload.get("result")
        if isinstance(result, dict):
            if record.get("decision") in (None, "") and result.get("decision"):
                record["decision"] = result["decision"]
            if record.get("summary") in (None, "") and result.get("summary"):
                record["summary"] = result["summary"]
            for key in ("artifact", "json"):
                value = result.get(key)
                if value and value not in record["files"]:
                    record["files"].append(value)


def iter_json_records(root: Path, directory: Path, source: str):
    if not directory.exists():
        return
    for path in sorted(directory.glob("*.json")):
        payload = load_json(path)
        file_id = normalize_experiment_id(path.name)
        payload_id = payload.get("experiment_id") if isinstance(payload, dict) else None
        experiment_id = normalize_experiment_id(payload_id) or file_id
        if experiment_id:
            yield (
                experiment_id,
                payload or {},
                canonical_source(source),
                canonical_identity_path(repo_relative(path, root)),
                file_id,
                payload_id,
            )


def iter_jsonl_records(root: Path, path: Path):
    if not path.exists():
        return
    try:
        with path.open(encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    payload = {}
                experiment_id = normalize_experiment_id(payload.get("experiment_id"))
                if experiment_id:
                    yield experiment_id, payload, "jsonl", f"{repo_relative(path, root)}:{line_number}"
    except OSError:
        return


def build_experiment_index(root=REPO_ROOT, registry_path=DEFAULT_REGISTRY, today=None):
    root = Path(root)
    registry_path = Path(registry_path)
    registry = load_registry(registry_path)
    registry["_repo_root"] = str(root)

    records = {}
    registry_ids = set()
    for entry in registry.get("experiments", []):
        experiment_id = normalize_experiment_id(entry.get("experiment_id"))
        if not experiment_id:
            continue
        registry_ids.add(experiment_id)
        merge_record(records, experiment_id, entry, "registry", repo_relative(registry_path, root))

    ticket_paths_by_id = defaultdict(list)
    duplicate_ticket_paths = {}
    mirrored_ticket_paths = {}
    for directory, source in (
        (root / "experiments" / "tickets", "ticket"),
        (root / "docs" / "experiments" / "tickets", "docs_ticket"),
    ):
        for item in iter_json_records(root, directory, source) or []:
            experiment_id, payload, item_source, path, file_id, payload_id = item
            ticket_paths_by_id[experiment_id].append((item_source, path, payload))
            merge_record(records, experiment_id, payload, item_source, path)
            if file_id and payload_id and normalize_experiment_id(payload_id) != file_id:
                records[experiment_id]["anomalies"].append("ticket_filename_id_mismatch")

    for experiment_id, ticket_items in ticket_paths_by_id.items():
        paths = [path for _, path, _ in ticket_items]
        source_types = {source for source, _, _ in ticket_items}
        if len(paths) > 1 and {"ticket", "docs_ticket"}.issubset(source_types):
            if matching_ticket_payloads(ticket_items):
                mirrored_ticket_paths[experiment_id] = paths
            else:
                duplicate_ticket_paths[experiment_id] = paths

    for directory, source in (
        (root / "experiments" / "logs", "log"),
        (root / "docs" / "experiments" / "logs", "docs_log"),
    ):
        for item in iter_json_records(root, directory, source) or []:
            experiment_id, payload, item_source, path, file_id, payload_id = item
            merge_record(records, experiment_id, payload, item_source, path)
            if file_id and payload_id and normalize_experiment_id(payload_id) != file_id:
                records[experiment_id]["anomalies"].append("log_filename_id_mismatch")

    for experiment_id, payload, source, path in iter_jsonl_records(
        root, root / "docs" / "experiment_log.jsonl"
    ) or []:
        merge_record(records, experiment_id, payload, source, path)

    for directory, source in (
        (root / "data" / "experiments", "data_experiment"),
        (root / "experiments" / "artifacts", "artifact"),
    ):
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            experiment_id = normalize_experiment_id(path.name)
            if experiment_id:
                merge_record(records, experiment_id, {}, source, repo_relative(path, root))

    source_map = collect_experiment_id_sources(registry, root=root)
    for experiment_id, sources in source_map.items():
        record = records.setdefault(
            experiment_id,
            default_record(experiment_id),
        )
        for source in sources:
            source_kind = source_kind_from_collected_source(source)
            if source_kind not in record["sources"]:
                record["sources"].append(source_kind)

    for experiment_id, record in records.items():
        sources = set(record.get("sources") or [])
        if experiment_id not in registry_ids:
            if should_count_missing_registry_as_anomaly(record, sources):
                record["anomalies"].append("missing_from_registry")
            else:
                record["identity_notes"].append("archive_missing_from_registry")
        if not TICKET_SOURCES.intersection(sources):
            if should_count_missing_ticket_as_anomaly(record, sources):
                record["anomalies"].append("missing_ticket")
            else:
                record["identity_notes"].append("archive_missing_ticket")
        if experiment_id in duplicate_ticket_paths:
            record["anomalies"].append("split_brain_ticket_paths")
            record["files"].extend(
                canonical_identity_path(path) for path in duplicate_ticket_paths[experiment_id]
                if path not in record["files"]
            )
        if experiment_id in mirrored_ticket_paths:
            record["identity_notes"].append("mirrored_ticket_paths")
            record["files"].extend(
                canonical_identity_path(path) for path in mirrored_ticket_paths[experiment_id]
                if path not in record["files"]
            )
        if "jsonl" in sources and not LOG_SOURCES.intersection(sources):
            if should_count_jsonl_log_gap_as_anomaly(record, sources):
                record["anomalies"].append("jsonl_without_per_experiment_log")
            else:
                record["identity_notes"].append("archive_jsonl_without_per_experiment_log")
        record["status_group"] = status_group(record)
        record["sources"] = sorted(sources)
        record["files"] = sorted(set(record.get("files") or []))
        record["anomalies"] = sorted(set(record.get("anomalies") or []))
        record["identity_notes"] = sorted(set(record.get("identity_notes") or []))
        record["metrics"] = derive_metrics(record)
        record["card"] = build_experiment_card(record)

    rows = sorted(records.values(), key=lambda row: row["experiment_id"], reverse=True)
    status_counts = Counter(row["status_group"] for row in rows)
    anomaly_counts = Counter(
        anomaly for row in rows for anomaly in row.get("anomalies", [])
    )
    identity_note_counts = Counter(
        note for row in rows for note in row.get("identity_notes", [])
    )

    return {
        "schema_version": 1,
        "generated_at": utc_now_iso(),
        "root": str(root),
        "registry_path": repo_relative(registry_path, root),
        "next_experiment_id": next_experiment_id(registry, today=today, root=root),
        "summary": {
            "experiment_count": len(rows),
            "registry_count": len(registry_ids),
            "status_counts": dict(sorted(status_counts.items())),
            "anomaly_counts": dict(sorted(anomaly_counts.items())),
            "anomaly_experiment_count": sum(1 for row in rows if row.get("anomalies")),
            "identity_note_counts": dict(sorted(identity_note_counts.items())),
            "identity_note_experiment_count": sum(
                1 for row in rows if row.get("identity_notes")
            ),
        },
        "leaderboards": build_leaderboards(rows),
        "dataset_view": build_dataset_view(rows),
        "collections": build_collections(rows),
        "experiments": rows,
    }


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ginger Experiment Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #18202a;
      --muted: #64707f;
      --line: #d8dee6;
      --panel: #f7f9fb;
      --good: #147a52;
      --bad: #b23b3b;
      --warn: #a56a00;
      --active: #2463a6;
      --observed: #6f4aa8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: #ffffff;
    }
    header {
      border-bottom: 1px solid var(--line);
      background: #ffffff;
      padding: 18px 24px 14px;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      letter-spacing: 0;
      font-weight: 700;
    }
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 18px;
      margin-top: 10px;
      color: var(--muted);
      font-size: 13px;
    }
    main { padding: 18px 24px 28px; }
    .summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      background: var(--panel);
      min-height: 72px;
    }
    .metric .label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }
    .metric .value {
      margin-top: 7px;
      font-size: 22px;
      font-weight: 700;
    }
    .controls {
      display: grid;
      grid-template-columns: minmax(220px, 1.3fr) 180px 180px 160px;
      gap: 10px;
      align-items: end;
      margin-bottom: 12px;
    }
    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 0 0 14px;
      border-bottom: 1px solid var(--line);
    }
    .tab {
      min-height: 34px;
      border: 1px solid var(--line);
      border-bottom: 0;
      border-radius: 6px 6px 0 0;
      padding: 7px 11px;
      background: #f8fafc;
      color: #344054;
      cursor: pointer;
      font: inherit;
    }
    .tab.active-tab {
      background: #ffffff;
      color: var(--ink);
      font-weight: 700;
    }
    label {
      display: grid;
      gap: 5px;
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
    }
    input, select {
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 9px;
      font: inherit;
      color: var(--ink);
      background: #ffffff;
    }
    .toggle {
      min-height: 36px;
      align-content: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 9px;
      background: #ffffff;
    }
    .toggle label {
      display: flex;
      gap: 8px;
      align-items: center;
      text-transform: none;
      color: var(--ink);
    }
    .toggle input { width: 16px; min-height: 16px; }
    .table-wrap {
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: auto;
      max-height: 68vh;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 1120px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 2;
      background: #eef2f6;
      color: #3d4854;
      font-size: 12px;
      text-transform: uppercase;
    }
    tr:hover td { background: #f8fbff; }
    .id { font-family: Consolas, "Courier New", monospace; white-space: nowrap; }
    .status {
      display: inline-block;
      min-width: 74px;
      border-radius: 999px;
      padding: 3px 7px;
      font-size: 12px;
      font-weight: 700;
      color: #ffffff;
      text-align: center;
    }
    .accepted { background: var(--good); }
    .rejected { background: var(--bad); }
    .active { background: var(--active); }
    .observed { background: var(--observed); }
    .proposed { background: var(--warn); }
    .unknown { background: #687383; }
    .chips { display: flex; flex-wrap: wrap; gap: 5px; }
    .chip {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 6px;
      color: #334155;
      background: #ffffff;
      font-size: 12px;
      white-space: nowrap;
    }
    .chip.warn {
      border-color: #e5b966;
      color: #7a4a00;
      background: #fff7e5;
    }
    .empty {
      padding: 28px;
      text-align: center;
      color: var(--muted);
      border: 1px solid var(--line);
      border-radius: 6px;
    }
    .panel-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(280px, 1fr));
      gap: 12px;
    }
    .surface {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #ffffff;
      padding: 14px;
    }
    .surface h2 {
      margin: 0 0 10px;
      font-size: 16px;
      letter-spacing: 0;
    }
    .surface h3 {
      margin: 0 0 8px;
      font-size: 14px;
      letter-spacing: 0;
    }
    .muted { color: var(--muted); }
    .card-list {
      display: grid;
      gap: 10px;
    }
    .experiment-card {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      background: #ffffff;
    }
    .card-head {
      display: flex;
      gap: 10px;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 8px;
    }
    .card-title {
      font-weight: 700;
      line-height: 1.3;
    }
    .card-summary {
      color: #344054;
      line-height: 1.4;
      margin-bottom: 9px;
    }
    .kv-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(120px, 1fr));
      gap: 7px;
      font-size: 12px;
    }
    .kv-grid div span {
      display: block;
      color: var(--muted);
      text-transform: uppercase;
      margin-bottom: 2px;
    }
    .bar-row {
      display: grid;
      grid-template-columns: minmax(130px, 0.8fr) 1fr 48px;
      gap: 8px;
      align-items: center;
      margin: 6px 0;
      font-size: 12px;
    }
    .bar {
      height: 9px;
      background: #e8edf3;
      border-radius: 999px;
      overflow: hidden;
    }
    .bar span {
      display: block;
      height: 100%;
      background: #5a8fca;
    }
    @media (max-width: 900px) {
      header, main { padding-left: 14px; padding-right: 14px; }
      .summary { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
      .controls { grid-template-columns: 1fr; }
      .table-wrap { max-height: none; }
      .panel-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Ginger Experiment Dashboard</h1>
    <div class="meta">
      <span id="generated"></span>
      <span id="next-id"></span>
      <span id="registry"></span>
    </div>
  </header>
  <main>
    <section class="summary" id="summary"></section>
    <nav class="tabs" aria-label="Dashboard views">
      <button class="tab active-tab" data-view="experiments">Experiments</button>
      <button class="tab" data-view="cards">Cards</button>
      <button class="tab" data-view="leaderboards">Leaderboards</button>
      <button class="tab" data-view="dataset">Dataset View</button>
      <button class="tab" data-view="collections">Collections</button>
    </nav>
    <section class="controls" aria-label="Filters">
      <label>Search<input id="search" type="search" autocomplete="off"></label>
      <label>Status<select id="status"></select></label>
      <label>Source<select id="source"></select></label>
      <div class="toggle"><label><input id="anomalies" type="checkbox"> anomalies only</label></div>
    </section>
    <section id="table"></section>
  </main>
  <script id="experiment-data" type="application/json">__INDEX_JSON__</script>
  <script>
    const index = JSON.parse(document.getElementById("experiment-data").textContent);
    const rows = index.experiments || [];
    const searchInput = document.getElementById("search");
    const statusSelect = document.getElementById("status");
    const sourceSelect = document.getElementById("source");
    const anomaliesOnly = document.getElementById("anomalies");
    let activeView = "experiments";

    function text(value) {
      return value == null ? "" : String(value);
    }
    function optionList(values) {
      return ["all"].concat(Array.from(new Set(values.filter(Boolean))).sort());
    }
    function fillSelect(select, values) {
      select.innerHTML = optionList(values).map(v => `<option value="${v}">${v}</option>`).join("");
    }
    function statusLabel(row) {
      return row.status_group || "unknown";
    }
    function rowBlob(row) {
      return [
        row.experiment_id, row.experiment_uid, row.status, row.decision, row.lane,
        row.owner, row.hypothesis, row.change_type, row.mechanism_family,
        row.trial_family, row.trial_variant_id, row.changed_variable,
        row.single_causal_variable, row.summary, (row.sources || []).join(" "),
        (row.anomalies || []).join(" "), (row.identity_notes || []).join(" ")
      ].map(text).join(" ").toLowerCase();
    }
    function esc(value) {
      return text(value).replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }
    function renderSummary() {
      const s = index.summary || {};
      const metrics = [
        ["Experiments", s.experiment_count],
        ["Registry Rows", s.registry_count],
        ["Anomaly Rows", s.anomaly_experiment_count || 0],
        ["Identity Notes", s.identity_note_experiment_count || 0],
        ["Accepted", (s.status_counts || {}).accepted || 0],
        ["Rejected", (s.status_counts || {}).rejected || 0]
      ];
      document.getElementById("summary").innerHTML = metrics.map(([label, value]) => (
        `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`
      )).join("");
      document.getElementById("generated").textContent = `Generated ${index.generated_at || ""}`;
      document.getElementById("next-id").textContent = `Next ${index.next_experiment_id || ""}`;
      document.getElementById("registry").textContent = index.registry_path || "";
    }
    function filteredRows() {
      const q = searchInput.value.trim().toLowerCase();
      const status = statusSelect.value;
      const source = sourceSelect.value;
      return rows.filter(row => {
        if (q && !rowBlob(row).includes(q)) return false;
        if (status !== "all" && statusLabel(row) !== status) return false;
        if (source !== "all" && !(row.sources || []).includes(source)) return false;
        if (anomaliesOnly.checked && !(row.anomalies || []).length) return false;
        return true;
      });
    }
    function chips(values, warn=false) {
      return `<div class="chips">${(values || []).map(v => `<span class="chip${warn ? " warn" : ""}">${esc(v)}</span>`).join("")}</div>`;
    }
    function fmtNumber(value) {
      const n = Number(value);
      if (value == null || !Number.isFinite(n)) return "";
      if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
      return n.toLocaleString(undefined, { maximumFractionDigits: 4 });
    }
    function metricText(metrics, key) {
      return fmtNumber((metrics || {})[key]);
    }
    function renderCard(row) {
      const card = row.card || {};
      const meta = card.metadata || {};
      return `
        <article class="experiment-card">
          <div class="card-head">
            <div>
              <div class="id">${esc(card.id || row.experiment_id)}</div>
              <div class="card-title">${esc(card.title || row.trial_family || "")}</div>
            </div>
            <span class="status ${esc(statusLabel(row))}">${esc(statusLabel(row))}</span>
          </div>
          <div class="card-summary">${esc(card.summary || "")}</div>
          <div class="kv-grid">
            <div><span>Lane</span>${esc(card.lane || "")}</div>
            <div><span>Trial</span>${esc(meta.trial_family || "")}</div>
            <div><span>Variable</span>${esc(meta.changed_variable || "")}</div>
            <div><span>EV Delta</span>${esc(metricText(card.metrics, "expected_value_score_delta"))}</div>
            <div><span>PnL Delta</span>${esc(metricText(card.metrics, "total_pnl_delta"))}</div>
            <div><span>Anomalies</span>${esc((card.anomalies || []).length)}</div>
            <div><span>Notes</span>${esc((card.identity_notes || []).length)}</div>
          </div>
        </article>`;
    }
    function renderCards() {
      const filtered = filteredRows().slice(0, 80);
      document.getElementById("table").innerHTML = `
        <section class="surface">
          <h2>Experiment Cards</h2>
          <p class="muted">Compact HF-style cards for the current filter. Showing ${filtered.length} of ${filteredRows().length} matches.</p>
          <div class="card-list">${filtered.map(renderCard).join("")}</div>
        </section>`;
    }
    function leaderboardTable(title, rows, metric) {
      const body = (rows || []).map(row => `
        <tr>
          <td class="id">${esc(row.experiment_id)}</td>
          <td>${esc(row.trial_family || row.mechanism_family || "")}</td>
          <td>${esc(row.changed_variable || "")}</td>
          <td>${esc(fmtNumber(row[metric]))}</td>
        </tr>`).join("");
      return `
        <section class="surface">
          <h2>${esc(title)}</h2>
          <div class="table-wrap"><table>
            <thead><tr><th>ID</th><th>Family</th><th>Variable</th><th>Value</th></tr></thead>
            <tbody>${body || `<tr><td colspan="4">No scored rows</td></tr>`}</tbody>
          </table></div>
        </section>`;
    }
    function renderLeaderboards() {
      const boards = index.leaderboards || {};
      const familyRows = (boards.rejected_families || []).map(row => `
        <tr><td>${esc(row.family)}</td><td>${esc(row.count)}</td></tr>`).join("");
      document.getElementById("table").innerHTML = `
        <div class="panel-grid">
          ${leaderboardTable("Top EV Delta", boards.top_ev_delta, "expected_value_score_delta")}
          ${leaderboardTable("Worst EV Delta", boards.bottom_ev_delta, "expected_value_score_delta")}
          ${leaderboardTable("Top PnL Delta", boards.top_pnl_delta, "total_pnl_delta")}
          <section class="surface">
            <h2>Rejected Families</h2>
            <div class="table-wrap"><table>
              <thead><tr><th>Family</th><th>Rejected</th></tr></thead>
              <tbody>${familyRows}</tbody>
            </table></div>
          </section>
        </div>`;
    }
    function renderDatasetView() {
      const columns = (index.dataset_view || {}).columns || [];
      const cards = columns.map(col => {
        const total = Math.max(1, Number(col.present || 0) + Number(col.missing || 0));
        const top = (col.top_values || []).slice(0, 8);
        return `
          <section class="surface">
            <h2>${esc(col.field)}</h2>
            <p class="muted">${esc(col.present)} present, ${esc(col.missing)} missing, ${esc(col.unique)} unique</p>
            ${top.map(item => {
              const pct = Math.round((Number(item.count || 0) / total) * 100);
              return `<div class="bar-row"><div>${esc(item.value)}</div><div class="bar"><span style="width:${pct}%"></span></div><div>${esc(item.count)}</div></div>`;
            }).join("")}
          </section>`;
      }).join("");
      document.getElementById("table").innerHTML = `<div class="panel-grid">${cards}</div>`;
    }
    function renderCollections() {
      const collectionRows = (index.collections || []).map(collection => `
        <section class="surface">
          <h2>${esc(collection.title)}</h2>
          <p class="muted">${esc(collection.description)}</p>
          <div class="metric"><div class="label">Experiments</div><div class="value">${esc(collection.count)}</div></div>
          <h3>Sample</h3>
          ${chips((collection.experiment_ids || []).slice(0, 30))}
        </section>`).join("");
      document.getElementById("table").innerHTML = `<div class="panel-grid">${collectionRows}</div>`;
    }
    function renderTable() {
      if (activeView === "cards") return renderCards();
      if (activeView === "leaderboards") return renderLeaderboards();
      if (activeView === "dataset") return renderDatasetView();
      if (activeView === "collections") return renderCollections();
      const filtered = filteredRows();
      if (!filtered.length) {
        document.getElementById("table").innerHTML = `<div class="empty">No matching experiments</div>`;
        return;
      }
      const body = filtered.map(row => `
        <tr>
          <td class="id">${esc(row.experiment_id)}</td>
          <td><span class="status ${esc(statusLabel(row))}">${esc(statusLabel(row))}</span></td>
          <td>${esc(row.lane || "")}</td>
          <td>${esc(row.trial_family || row.mechanism_family || "")}</td>
          <td>${esc(row.changed_variable || row.single_causal_variable || "")}</td>
          <td>${esc(row.hypothesis || row.summary || "")}</td>
          <td>${chips(row.sources || [])}</td>
          <td>${chips(row.anomalies || [], true)}</td>
          <td>${chips(row.identity_notes || [])}</td>
        </tr>`).join("");
      document.getElementById("table").innerHTML = `
        <div class="table-wrap">
          <table>
            <thead><tr>
              <th>ID</th><th>Status</th><th>Lane</th><th>Family</th>
              <th>Variable</th><th>Hypothesis / Summary</th><th>Sources</th><th>Anomalies</th><th>Notes</th>
            </tr></thead>
            <tbody>${body}</tbody>
          </table>
        </div>`;
    }
    fillSelect(statusSelect, rows.map(statusLabel));
    fillSelect(sourceSelect, rows.flatMap(row => row.sources || []));
    renderSummary();
    renderTable();
    document.querySelectorAll(".tab").forEach(tab => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(other => other.classList.remove("active-tab"));
        tab.classList.add("active-tab");
        activeView = tab.dataset.view;
        renderTable();
      });
    });
    [searchInput, statusSelect, sourceSelect, anomaliesOnly].forEach(el => {
      el.addEventListener("input", renderTable);
      el.addEventListener("change", renderTable);
    });
  </script>
</body>
</html>
"""


def write_dashboard(index, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "experiment_index.json"
    html_path = output_dir / "index.html"
    safe_index = clean_for_json(index)
    json_payload = json.dumps(safe_index, ensure_ascii=False, indent=2, allow_nan=False)
    json_path.write_text(json_payload + "\n", encoding="utf-8")
    embedded = (
        json.dumps(safe_index, ensure_ascii=False, allow_nan=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    html_path.write_text(HTML_TEMPLATE.replace("__INDEX_JSON__", embedded), encoding="utf-8")
    return html_path, json_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "experiments" / "dashboard"))
    parser.add_argument("--today", help="Override YYYYMMDD prefix for testing.")
    parser.add_argument("--json", action="store_true", help="Print the index JSON to stdout.")
    args = parser.parse_args()

    index = build_experiment_index(args.root, args.registry, today=args.today)
    html_path, json_path = write_dashboard(index, args.output_dir)
    if args.json:
        print(json.dumps(index, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({
            "html": str(html_path),
            "json": str(json_path),
            "next_experiment_id": index["next_experiment_id"],
            "summary": index["summary"],
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
