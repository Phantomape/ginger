"""Build a static experiment registry dashboard.

The dashboard is read-only. It indexes experiment records across the registry,
JSONL log, per-experiment tickets/logs, artifacts, and data directories so ID
allocation gaps are visible before the next ticket is created.
"""

from __future__ import annotations

import argparse
import json
import math
import re
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
    "ticket_file",
    "log_file",
    "card_file",
    "revision_manifest_file",
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

FORWARD_EVIDENCE_DEFAULT_TARGET = 20
SURFACE_SLEEVE_ALIASES = (
    (("state_surface", "state surface", "satellite"), ("state_surface", "state_surface_satellite_paper")),
    (("broad_market", "broad market", "leadership"), ("broad_market", "broad_market_leadership_paper")),
    (("volatility", "qqq-confirmed", "qqq confirmed", "vcp"), ("volatility_contraction", "volatility_contraction_qqq_confirmed_paper")),
    (("sec financial", "financial-report", "financial report"), ("sec_financial_report", "sec_financial_report_paper")),
    (("sec negative", "negative / governance", "procedural queues"), ("sec_negative", "sec_governance", "sec_leadership")),
    (("external event", "event overlay"), ("volume_breadth_breakout", "form4")),
    (("space catalyst",), ("space_catalyst",)),
    (("core_misfit", "core-misfit", "core misfit"), ("core_misfit", "core_misfit_paper")),
    (("low-deployment etf", "low deployment etf"), ("low_deployment_etf",)),
    (("ai optical", "optical"), ("ai_optical",)),
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


def experiment_order(experiment_id: str):
    match = re.match(r"exp-(\d{8})-(\d{3})$", str(experiment_id or ""))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def is_later_experiment(candidate_id: str, source_id: str) -> bool:
    candidate_order = experiment_order(candidate_id)
    source_order = experiment_order(source_id)
    if candidate_order is None or source_order is None:
        return str(candidate_id or "") > str(source_id or "")
    return candidate_order > source_order


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


def is_rejected_high_upside(row: dict) -> bool:
    metrics = derive_metrics(row)
    ev_delta = metrics.get("expected_value_score_delta")
    pnl_delta = metrics.get("total_pnl_delta")
    return row.get("status_group") == "rejected" and (
        (ev_delta is not None and ev_delta > 0)
        or (pnl_delta is not None and pnl_delta > 0)
    )


def rejected_upside_sort_key(row: dict):
    ev_delta = row.get("expected_value_score_delta")
    pnl_delta = row.get("total_pnl_delta")
    return (
        ev_delta is not None,
        ev_delta if ev_delta is not None else float("-inf"),
        pnl_delta is not None,
        pnl_delta if pnl_delta is not None else float("-inf"),
        row.get("experiment_id") or "",
    )


def high_after_ev_sort_key(row: dict):
    after_ev = row.get("after_expected_value_score")
    ev_delta = row.get("expected_value_score_delta")
    return (
        after_ev is not None,
        after_ev if after_ev is not None else float("-inf"),
        ev_delta is not None,
        ev_delta if ev_delta is not None else float("-inf"),
        row.get("experiment_id") or "",
    )


def followup_match_evidence(source: dict, candidate: dict) -> list[str]:
    source_id = source.get("experiment_id")
    evidence = []
    if source_id and source_id.lower() in _row_text(candidate):
        evidence.append("explicit_ref")
    for key, label in (
        ("trial_family", "same_trial_family"),
        ("mechanism_family", "same_mechanism_family"),
    ):
        source_value = source.get(key)
        if source_value and source_value == candidate.get(key):
            evidence.append(label)
    return evidence


def build_accepted_followup_index(rows: list[dict], source_rows: list[dict]) -> dict[str, list[dict]]:
    accepted_rows = [
        row for row in rows
        if row.get("status_group") == "accepted"
    ]
    followups_by_source = {}
    for source in source_rows:
        source_id = source.get("experiment_id")
        if not source_id:
            continue
        followups = []
        for candidate in accepted_rows:
            candidate_id = candidate.get("experiment_id")
            if not candidate_id or not is_later_experiment(candidate_id, source_id):
                continue
            evidence = followup_match_evidence(source, candidate)
            if not evidence:
                continue
            metrics = derive_metrics(candidate)
            followups.append({
                "experiment_id": candidate_id,
                "status_group": candidate.get("status_group"),
                "trial_family": candidate.get("trial_family"),
                "mechanism_family": candidate.get("mechanism_family"),
                "changed_variable": candidate.get("changed_variable")
                or candidate.get("single_causal_variable"),
                "evidence": evidence,
                **metrics,
            })
        followups.sort(key=high_after_ev_sort_key, reverse=True)
        followups_by_source[source_id] = followups[:8]
    return followups_by_source


def attach_followups(source_rows: list[dict], followups_by_source: dict[str, list[dict]]) -> list[dict]:
    enriched = []
    for row in source_rows:
        copied = dict(row)
        followups = followups_by_source.get(row.get("experiment_id"), [])
        copied["accepted_followups"] = followups
        copied["accepted_followup_ids"] = [
            followup["experiment_id"] for followup in followups
        ]
        copied["has_accepted_followup"] = bool(followups)
        enriched.append(copied)
    return enriched


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
    high_after_ev = sorted(
        [
            row for row in scored
            if row.get("after_expected_value_score") is not None
            and row["after_expected_value_score"] > 10
        ],
        key=high_after_ev_sort_key,
        reverse=True,
    )[:50]
    rejected_high_upside = sorted(
        [row for row in scored if is_rejected_high_upside(row)],
        key=rejected_upside_sort_key,
        reverse=True,
    )[:50]
    rejected_high_after_ev = [
        row for row in high_after_ev
        if row.get("status_group") == "rejected"
    ][:50]
    rejected_lineage_sources = {
        row["experiment_id"]: row
        for row in rejected_high_upside + rejected_high_after_ev
        if row.get("experiment_id")
    }
    followups_by_source = build_accepted_followup_index(
        rows,
        list(rejected_lineage_sources.values()),
    )
    rejected_high_upside = attach_followups(
        rejected_high_upside,
        followups_by_source,
    )
    rejected_high_after_ev = attach_followups(
        rejected_high_after_ev,
        followups_by_source,
    )
    unresolved_rejected_high_after_ev = [
        row for row in rejected_high_after_ev
        if not row.get("has_accepted_followup")
    ]
    resolved_rejected_high_after_ev = [
        row for row in rejected_high_after_ev
        if row.get("has_accepted_followup")
    ]
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
        "high_after_ev": high_after_ev,
        "rejected_high_after_ev": rejected_high_after_ev,
        "unresolved_rejected_high_after_ev": unresolved_rejected_high_after_ev,
        "resolved_rejected_high_after_ev": resolved_rejected_high_after_ev,
        "rejected_high_upside": rejected_high_upside,
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
    rejected_high_upside = sorted(
        [row for row in rows if is_rejected_high_upside(row)],
        key=lambda row: rejected_upside_sort_key({
            "experiment_id": row.get("experiment_id"),
            **derive_metrics(row),
        }),
        reverse=True,
    )
    collections.append({
        "slug": "rejected_high_upside",
        "title": "Rejected High-Upside",
        "description": "Rejected experiments with positive EV or PnL deltas. These failed Gate 4 or other constraints, but preserve alpha clues worth revisiting with new evidence.",
        "count": len(rejected_high_upside),
        "experiment_ids": [row.get("experiment_id") for row in rejected_high_upside[:200]],
    })
    return collections


def _slug(value) -> str:
    text = str(value or "").lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _compact_text(value, limit=260) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _list_value(payload: dict, key: str) -> list:
    value = payload.get(key)
    return value if isinstance(value, list) else []


def _collect_tickers(value, tickers: set[str], limit=12):
    if len(tickers) >= limit:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"ticker", "symbol", "pilot_ticker"} and isinstance(item, str):
                ticker = item.strip().upper()
                if ticker:
                    tickers.add(ticker)
                    if len(tickers) >= limit:
                        return
            else:
                _collect_tickers(item, tickers, limit=limit)
    elif isinstance(value, list):
        for item in value:
            _collect_tickers(item, tickers, limit=limit)
            if len(tickers) >= limit:
                return


def _sum_numeric(items, keys):
    total = 0.0
    found = False
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in keys:
            number = _as_number(item.get(key))
            if number is not None:
                total += number
                found = True
                break
    return round(total, 2) if found else None


def summarize_paper_sleeve_file(root: Path, path: Path):
    payload = load_json(path)
    if not isinstance(payload, dict):
        return None
    relative = repo_relative(path, root)
    slug = _slug(path.parent.name)
    open_positions = _list_value(payload, "open_positions")
    pending_entries = _list_value(payload, "pending_entries")
    closed_positions = _list_value(payload, "closed_positions")
    skipped_entries = _list_value(payload, "skipped_entries")
    tickers = set()
    _collect_tickers({
        "open_positions": open_positions,
        "pending_entries": pending_entries,
        "closed_positions": closed_positions,
        "candidates": payload.get("candidates"),
    }, tickers)
    ledger_rows = first_number(payload, [
        ("ledger_row_count",),
        ("row_count",),
        ("forward_row_count",),
        ("observation_count",),
    ])
    candidate_count = first_number(payload, [
        ("candidate_count",),
        ("selected_count",),
        ("signal_count",),
        ("ten_k_event_count",),
    ])
    forward_target = first_number(payload, [
        ("parameters", "forward_gate_min_closed_trades"),
        ("tail_diagnostics", "gate_report", "thresholds", "min_trades_for_promotion"),
    ])
    sleeve_name = (
        payload.get("sleeve")
        or payload.get("watch_name")
        or payload.get("rule_version")
        or path.parent.name
    )
    return {
        "slug": slug,
        "sleeve": str(sleeve_name),
        "file": relative,
        "source_kind": path.name,
        "updated_at": payload.get("updated_at") or payload.get("asof_date") or payload.get("as_of"),
        "open_count": len(open_positions),
        "pending_count": len(pending_entries),
        "closed_count": len(closed_positions),
        "skipped_count": len(skipped_entries),
        "ledger_row_count": int(ledger_rows) if ledger_rows is not None else None,
        "candidate_count": int(candidate_count) if candidate_count is not None else None,
        "forward_target_count": int(forward_target) if forward_target is not None else None,
        "ticker_sample": sorted(tickers)[:12],
        "unrealized_pnl": _sum_numeric(open_positions, ("unrealized_pnl", "net_pnl_if_closed_now")),
        "closed_pnl": _sum_numeric(closed_positions, ("net_pnl", "pnl", "realized_pnl")),
        "alters_orders": bool(_nested_get(payload, ("production_impact", "alters_orders"))),
        "trade_enabled": any(
            bool(item.get("trade_enabled"))
            for item in open_positions + pending_entries + closed_positions
            if isinstance(item, dict)
        ),
    }


def collect_paper_sleeves(root: Path):
    sleeve_dir = root / "data" / "paper_sleeves"
    if not sleeve_dir.exists():
        return []
    sleeves = []
    for path in sorted(sleeve_dir.rglob("*.json")):
        if path.name not in {"state.json", "summary.json", "observation_slot_summary.json", "event_state_shadow_summary.json"}:
            continue
        summary = summarize_paper_sleeve_file(root, path)
        if summary:
            sleeves.append(summary)
    return sleeves


def _snapshot_count(payload: dict, direct_paths, list_key: str):
    number = first_number(payload, direct_paths)
    if number is not None:
        return int(number)
    value = payload.get(list_key)
    return len(value) if isinstance(value, list) else 0


def summarize_snapshot_payload(payload: dict):
    if not isinstance(payload, dict):
        return None
    closed_count = _snapshot_count(payload, [
        ("closed_position_count",),
        ("closed_count",),
        ("replacement_value_report", "closed_count"),
        ("forward_paper_gate", "metrics", "closed_trades"),
    ], "closed_positions")
    open_count = _snapshot_count(payload, [
        ("open_position_count",),
        ("open_count",),
        ("replacement_value_report", "open_count"),
    ], "open_positions")
    pending_count = _snapshot_count(payload, [
        ("pending_count",),
        ("replacement_value_report", "pending_count"),
    ], "pending_entries")
    target_count = first_number(payload, [
        ("parameters", "forward_gate_min_closed_trades"),
        ("tail_diagnostics", "gate_report", "thresholds", "min_trades_for_promotion"),
    ])
    realized_pnl = first_number(payload, [
        ("realized_pnl_to_date",),
        ("replacement_value_report", "closed_pnl"),
        ("forward_paper_gate", "metrics", "realized_pnl"),
    ])
    unrealized_pnl = first_number(payload, [
        ("unrealized_pnl",),
        ("replacement_value_report", "open_unrealized_pnl"),
    ])
    date = payload.get("asof_date") or payload.get("as_of")
    if not date and payload.get("generated_at"):
        date = str(payload["generated_at"])[:10]
    if not date and payload.get("updated_at"):
        date = str(payload["updated_at"])[:10]
    target = int(target_count) if target_count else None
    closed_pct = round(min(100.0, closed_count / target * 100.0), 2) if target else 0.0
    pipeline_pct = (
        round(min(100.0, (closed_count + 0.55 * open_count + 0.2 * pending_count) / target * 100.0), 2)
        if target
        else 0.0
    )
    return {
        "date": str(date or ""),
        "closed_count": closed_count,
        "open_count": open_count,
        "pending_count": pending_count,
        "target_count": target,
        "closed_pct": closed_pct,
        "pipeline_pct": pipeline_pct,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
    }


def collect_evidence_curves(root: Path):
    sleeve_dir = root / "data" / "paper_sleeves"
    if not sleeve_dir.exists():
        return []
    curves = []
    for path in sorted(sleeve_dir.rglob("snapshots.jsonl")):
        points = []
        sleeve_name = path.parent.name
        try:
            with path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    point = summarize_snapshot_payload(payload)
                    if not point:
                        continue
                    if isinstance(payload, dict):
                        sleeve_name = payload.get("sleeve") or payload.get("watch_name") or sleeve_name
                    points.append(point)
        except OSError:
            continue
        if not points:
            continue
        latest = points[-1]
        target = latest.get("target_count")
        closed = latest.get("closed_count") or 0
        open_count = latest.get("open_count") or 0
        pending_count = latest.get("pending_count") or 0
        curves.append({
            "slug": _slug(path.parent.name),
            "sleeve": str(sleeve_name),
            "file": repo_relative(path, root),
            "point_count": len(points),
            "latest_date": latest.get("date"),
            "target_count": target,
            "closed_count": closed,
            "open_count": open_count,
            "pending_count": pending_count,
            "remaining_closed": max(target - closed, 0) if target is not None else None,
            "closed_pct": latest.get("closed_pct"),
            "pipeline_pct": latest.get("pipeline_pct"),
            "points": points[-40:],
        })
    curves.sort(
        key=lambda curve: (
            curve.get("target_count") is None,
            -(curve.get("pipeline_pct") or 0),
            -(curve.get("open_count") or 0),
            curve.get("sleeve") or "",
        )
    )
    return curves


def parse_activation_map(root: Path):
    path = root / "docs" / "current_state.md"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    in_section = False
    in_table = False
    headers = []
    for line in lines:
        if line.startswith("## "):
            if in_section and in_table:
                break
            in_section = "Return Constraint / Activation Map" in line
            in_table = False
            continue
        if not in_section:
            continue
        if not line.strip().startswith("|"):
            if in_table:
                break
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r"[:\-\s]+", cell or "") for cell in cells):
            continue
        if not headers:
            headers = [_slug(cell) for cell in cells]
            in_table = True
            continue
        row = dict(zip(headers, cells))
        if row.get("surface"):
            rows.append(row)
    return rows


def classify_activation_surface(row: dict) -> str:
    text = " ".join(str(value or "") for value in row.values()).lower()
    status = str(row.get("default_execution_status") or "").lower()
    if "trade-enabled default path" in text:
        return "executing"
    if "live slots are zero" in text or "no live space slots" in text:
        return "blocked"
    if "replay-only" in text and "paper" not in status and "default-off" not in status:
        return "replay_only"
    if any(token in text for token in ("default-off", "paper", "observe-only", "closed forward", "forward replacement", "forward gate")):
        return "forward_accumulating"
    if any(token in text for token in (
        "production can emit",
        "production advisory",
        "production live path exists",
        "manual/live execution",
    )):
        return "executing"
    if "no explicit trade adapter" in text or "trade adapter" in text:
        return "blocked"
    return "unknown"


def infer_required_closed_forward(row: dict):
    text = " ".join(str(value or "") for value in row.values()).lower()
    patterns = (
        r"at least\s+(\d+)\s+closed",
        r"(\d+)\s+closed\s+(?:forward\s+)?(?:paper\s+)?outcomes",
        r"(\d+)\s+closed\s+\d+-day\s+paper\s+outcomes",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1)), "explicit"
    if any(token in text for token in (
        "closed forward",
        "closed replacement-value",
        "forward replacement-value",
        "forward gate",
        "replacement-value gate",
    )):
        return FORWARD_EVIDENCE_DEFAULT_TARGET, "dashboard_default_forward_gate"
    return None, None


def sleeve_matches_surface(surface: dict, sleeve: dict) -> bool:
    surface_text = " ".join(str(value or "") for value in surface.values()).lower()
    sleeve_text = " ".join(
        str(sleeve.get(key) or "")
        for key in ("slug", "sleeve", "file")
    ).lower()
    surface_slug = _slug(surface_text)
    sleeve_slug = _slug(sleeve_text)
    if sleeve.get("slug") and _slug(sleeve["slug"]) in surface_slug:
        return True
    for surface_terms, sleeve_terms in SURFACE_SLEEVE_ALIASES:
        surface_hit = any(term in surface_text or _slug(term) in surface_slug for term in surface_terms)
        sleeve_hit = any(term in sleeve_text or _slug(term) in sleeve_slug for term in sleeve_terms)
        if surface_hit and sleeve_hit:
            return True
    return False


def surface_gap_label(row: dict, state: str, closed_count: int, required: int | None, gap: int | None):
    text = " ".join(str(value or "") for value in row.values()).lower()
    if state == "executing":
        return "Executing in the current production path."
    if required is not None:
        if gap and gap > 0:
            return f"Needs {gap} more closed forward outcomes before activation review."
        return "Closed-forward sample target is met; review replacement value, drawdown, and concentration."
    if "live slots are zero" in text:
        return "Live slots are zero; needs a separate pilot promotion."
    if "explicit trade adapter" in text or "no trade-enabled adapter" in text:
        return "Needs an explicit trade adapter plus forward replacement-value evidence."
    if "replay-only" in text:
        return "Replay-only evidence; needs a forward ledger before promotion."
    if closed_count == 0 and "paper" in text:
        return "Paper ledger exists but has no closed outcomes yet."
    return "Target is not declared in current_state.md."


def build_activation_surfaces(root: Path, sleeves):
    surfaces = []
    for row in parse_activation_map(root):
        state = classify_activation_surface(row)
        required, target_basis = infer_required_closed_forward(row)
        matched = [sleeve for sleeve in sleeves if sleeve_matches_surface(row, sleeve)]
        open_count = sum(sleeve.get("open_count") or 0 for sleeve in matched)
        pending_count = sum(sleeve.get("pending_count") or 0 for sleeve in matched)
        closed_count = sum(sleeve.get("closed_count") or 0 for sleeve in matched)
        skipped_count = sum(sleeve.get("skipped_count") or 0 for sleeve in matched)
        tickers = sorted({
            ticker
            for sleeve in matched
            for ticker in sleeve.get("ticker_sample") or []
        })[:12]
        matched_targets = [
            sleeve.get("forward_target_count")
            for sleeve in matched
            if sleeve.get("forward_target_count") is not None
        ]
        if matched_targets and (required is None or target_basis == "dashboard_default_forward_gate"):
            required = max(matched_targets)
            target_basis = "paper_sleeve_forward_gate"
        gap = max(required - closed_count, 0) if required is not None else None
        limits = row.get("limits") or row.get("what_limits_realized_return")
        activation_lever = row.get("activation_lever") or row.get("aggressive_activation_lever")
        risk = row.get("risk") or row.get("main_risk_if_enabled")
        surfaces.append({
            "surface": row.get("surface"),
            "state": state,
            "stage_label": {
                "executing": "Executing",
                "forward_accumulating": "Forward accumulating",
                "replay_only": "Replay/default-off",
                "blocked": "Blocked",
            }.get(state, "Unknown"),
            "default_execution_status": row.get("default_execution_status"),
            "current_evidence": _compact_text(row.get("current_evidence"), limit=420),
            "limits": _compact_text(limits, limit=360),
            "activation_lever": _compact_text(activation_lever, limit=260),
            "risk": _compact_text(risk, limit=260),
            "matched_sleeves": [sleeve.get("slug") for sleeve in matched],
            "paper_open_count": open_count,
            "paper_pending_count": pending_count,
            "paper_closed_count": closed_count,
            "paper_skipped_count": skipped_count,
            "required_closed_forward": required,
            "target_basis": target_basis,
            "evidence_gap": gap,
            "gap_label": surface_gap_label(row, state, closed_count, required, gap),
            "ticker_sample": tickers,
        })
    return surfaces


def summarize_live_positions(root: Path):
    payload = load_json(root / "operator_inputs" / "open_positions.json")
    if not isinstance(payload, dict):
        return {
            "count": 0,
            "positions_count": 0,
            "observations_count": 0,
            "ticker_sample": [],
            "strategy_counts": {},
        }
    positions = _list_value(payload, "positions")
    observations = _list_value(payload, "observations")
    all_rows = positions + observations
    tickers = sorted({
        str(row.get("ticker")).upper()
        for row in all_rows
        if isinstance(row, dict) and row.get("ticker")
    })
    strategy_counts = Counter(
        str(row.get("opened_by_strategy") or "unknown")
        for row in all_rows
        if isinstance(row, dict)
    )
    return {
        "as_of": payload.get("as_of"),
        "account": payload.get("account"),
        "portfolio_value_usd": payload.get("portfolio_value_usd"),
        "count": len(all_rows),
        "positions_count": len(positions),
        "observations_count": len(observations),
        "ticker_sample": tickers[:18],
        "strategy_counts": dict(strategy_counts.most_common(12)),
    }


def summarize_pilot_decisions(root: Path):
    path = root / "data" / "ledgers" / "pilot_competition_decisions.jsonl"
    if not path.exists():
        return None
    count = 0
    tradeable_count = 0
    last_timestamp = None
    tickers = set()
    sleeves = Counter()
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                count += 1
                last_timestamp = payload.get("timestamp") or payload.get("logged_at") or last_timestamp
                sleeve = payload.get("sleeve") or _nested_get(payload, ("risk_snapshot", "pilot_sleeve", "name"))
                if sleeve:
                    sleeves[str(sleeve)] += 1
                ticker = payload.get("pilot_ticker")
                if ticker:
                    tickers.add(str(ticker).upper())
                if _nested_get(payload, ("risk_snapshot", "pilot_sizing", "pilot_sleeve_tradeable")) is True:
                    tradeable_count += 1
    except OSError:
        return None
    if not count:
        return None
    return {
        "decision_count": count,
        "tradeable_count": tradeable_count,
        "last_timestamp": last_timestamp,
        "ticker_sample": sorted(tickers)[:12],
        "sleeve_counts": dict(sleeves.most_common(8)),
        "file": repo_relative(path, root),
    }


def append_pilot_surface(surfaces, pilot):
    if not pilot:
        return
    for surface in surfaces:
        if "AI_INFRA_AGGRESSIVE" not in str(surface.get("surface") or ""):
            continue
        if pilot.get("tradeable_count"):
            surface["state"] = "executing"
            surface["stage_label"] = "Executing"
        surface["paper_pending_count"] = pilot.get("decision_count") or 0
        surface["ticker_sample"] = pilot.get("ticker_sample") or surface.get("ticker_sample") or []
        surface["gap_label"] = "Pilot sleeve is emitting tradeable decision snapshots; promotion still needs closed evidence review."
        surface["current_evidence"] = (
            f"{pilot.get('decision_count')} pilot decision snapshots; "
            f"{pilot.get('tradeable_count')} marked tradeable."
        )
        return
    surfaces.append({
        "surface": "AI_INFRA_AGGRESSIVE pilot sleeve",
        "state": "executing" if pilot.get("tradeable_count") else "forward_accumulating",
        "stage_label": "Executing" if pilot.get("tradeable_count") else "Forward accumulating",
        "default_execution_status": "Pilot sleeve decision snapshots",
        "current_evidence": f"{pilot.get('decision_count')} pilot decision snapshots; {pilot.get('tradeable_count')} marked tradeable.",
        "limits": "Pilot ledger only; promotion and sizing remain governed by the pilot protocol.",
        "activation_lever": "Keep monitoring replacement value and concentration before any broader core expansion.",
        "risk": "Theme and single-name concentration.",
        "matched_sleeves": [],
        "paper_open_count": 0,
        "paper_pending_count": pilot.get("decision_count") or 0,
        "paper_closed_count": 0,
        "paper_skipped_count": 0,
        "required_closed_forward": None,
        "target_basis": None,
        "evidence_gap": None,
        "gap_label": "Pilot sleeve is emitting tradeable decision snapshots; promotion still needs closed evidence review.",
        "ticker_sample": pilot.get("ticker_sample") or [],
    })


def build_production_compare(root=REPO_ROOT):
    root = Path(root)
    sleeves = collect_paper_sleeves(root)
    evidence_curves = collect_evidence_curves(root)
    surfaces = build_activation_surfaces(root, sleeves)
    pilot = summarize_pilot_decisions(root)
    append_pilot_surface(surfaces, pilot)
    state_counts = Counter(surface.get("state") for surface in surfaces)
    paper_closed = sum(sleeve.get("closed_count") or 0 for sleeve in sleeves)
    paper_open = sum(sleeve.get("open_count") or 0 for sleeve in sleeves)
    paper_pending = sum(sleeve.get("pending_count") or 0 for sleeve in sleeves)
    known_gap_count = sum(
        1
        for surface in surfaces
        if (surface.get("evidence_gap") or 0) > 0
        or surface.get("state") in {"blocked", "replay_only"}
    )
    return {
        "summary": {
            "surface_count": len(surfaces),
            "executing_count": state_counts.get("executing", 0),
            "forward_accumulating_count": state_counts.get("forward_accumulating", 0),
            "replay_only_count": state_counts.get("replay_only", 0),
            "blocked_count": state_counts.get("blocked", 0),
            "known_gap_count": known_gap_count,
            "paper_open_count": paper_open,
            "paper_pending_count": paper_pending,
            "paper_closed_count": paper_closed,
        },
        "surfaces": surfaces,
        "paper_sleeves": sleeves,
        "evidence_curves": evidence_curves,
        "live_positions": summarize_live_positions(root),
        "pilot_decisions": pilot,
        "generated_from": [
            "docs/current_state.md",
            "operator_inputs/open_positions.json",
            "data/paper_sleeves/**/*.json",
            "data/ledgers/pilot_competition_decisions.jsonl",
        ],
    }


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
        for key in ("ticket_file", "log_file", "card_file", "revision_manifest_file"):
            value = payload.get(key)
            if value:
                value = canonical_identity_path(value)
                if value not in record["files"]:
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

    for item in iter_json_records(root, root / "experiments" / "manifests", "manifest") or []:
        experiment_id, payload, item_source, path, file_id, payload_id = item
        merge_record(records, experiment_id, payload, item_source, path)
        if file_id and payload_id and normalize_experiment_id(payload_id) != file_id:
            records[experiment_id]["anomalies"].append("manifest_filename_id_mismatch")

    cards_dir = root / "experiments" / "cards"
    if cards_dir.exists():
        for path in sorted(cards_dir.glob("*.md")):
            experiment_id = normalize_experiment_id(path.name)
            if experiment_id:
                merge_record(records, experiment_id, {}, "card", repo_relative(path, root))

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
        "production_compare": build_production_compare(root),
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
      color-scheme: dark;
      --ink: #abb2bf;
      --bright: #e6edf3;
      --muted: #9aa4b5;
      --subtle: #747d8d;
      --line: #434957;
      --soft-line: #333944;
      --page: #1b1f27;
      --page-deep: #171a21;
      --panel: #282c34;
      --panel-raised: #303642;
      --panel-soft: #2b313c;
      --panel-deep: #20242c;
      --blue: #61afef;
      --blue-soft: rgba(97, 175, 239, 0.13);
      --green: #98c379;
      --green-soft: rgba(152, 195, 121, 0.13);
      --red: #e06c75;
      --red-soft: rgba(224, 108, 117, 0.13);
      --amber: #e5c07b;
      --amber-soft: rgba(229, 192, 123, 0.13);
      --violet: #c678dd;
      --violet-soft: rgba(198, 120, 221, 0.13);
      --cyan: #56b6c2;
      --cyan-soft: rgba(86, 182, 194, 0.13);
      --orange: #d19a66;
      --shadow: 0 16px 38px rgba(0, 0, 0, 0.34);
    }
    *,
    *::before,
    *::after {
      box-sizing: border-box;
      min-width: 0;
    }
    body {
      margin: 0;
      color: var(--ink);
      background: linear-gradient(180deg, var(--page) 0%, #21252b 46%, var(--page-deep) 100%);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      overflow-x: hidden;
      text-rendering: optimizeLegibility;
    }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      background: rgba(27, 31, 39, 0.97);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(10px);
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
    }
    .topbar-inner {
      max-width: 1680px;
      margin: 0 auto;
      padding: 18px 28px 14px;
    }
    .title-row {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      letter-spacing: 0;
      color: var(--bright);
      overflow-wrap: anywhere;
    }
    .subtitle {
      margin: 6px 0 0;
      color: var(--muted);
      line-height: 1.45;
      max-width: 760px;
    }
    .meta-pills {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
      min-width: 280px;
      max-width: 720px;
    }
    .pill,
    .chip {
      display: inline-flex;
      align-items: center;
      max-width: 100%;
      min-height: 24px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 8px;
      background: rgba(48, 54, 66, 0.82);
      color: var(--ink);
      font-size: 12px;
      line-height: 1.25;
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .pill strong {
      margin-left: 5px;
      color: var(--bright);
      font-weight: 700;
      overflow-wrap: anywhere;
    }
    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 16px;
    }
    .tab {
      min-height: 34px;
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 7px 12px;
      background: transparent;
      color: var(--ink);
      cursor: pointer;
      font: inherit;
      font-size: 14px;
      line-height: 1.25;
      transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
    }
    .tab:hover { background: var(--panel-soft); }
    .tab.active-tab {
      border-color: rgba(97, 175, 239, 0.48);
      background: linear-gradient(180deg, rgba(97, 175, 239, 0.12), rgba(97, 175, 239, 0.05));
      color: var(--amber);
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
    }
    main {
      max-width: 1680px;
      margin: 0 auto;
      padding: 18px 28px 30px;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(6, minmax(120px, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }
    .metric {
      --metric-accent: var(--blue);
      --metric-bg: var(--blue-soft);
      position: relative;
      overflow: hidden;
      min-height: 76px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: linear-gradient(180deg, var(--metric-bg), rgba(40, 44, 52, 0.98));
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.22);
    }
    .metric::before {
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 3px;
      background: var(--metric-accent);
    }
    .metric.tone-blue { --metric-accent: var(--blue); --metric-bg: var(--blue-soft); }
    .metric.tone-violet { --metric-accent: var(--violet); --metric-bg: var(--violet-soft); }
    .metric.tone-amber { --metric-accent: var(--amber); --metric-bg: var(--amber-soft); }
    .metric.tone-green { --metric-accent: var(--green); --metric-bg: var(--green-soft); }
    .metric.tone-red { --metric-accent: var(--red); --metric-bg: var(--red-soft); }
    .metric.tone-cyan { --metric-accent: var(--cyan); --metric-bg: var(--cyan-soft); }
    .metric .label {
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .metric .value {
      margin-top: 8px;
      font-size: 24px;
      line-height: 1.1;
      font-weight: 750;
      color: var(--metric-accent);
    }
    .hub-shell {
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr) 360px;
      gap: 16px;
      align-items: start;
    }
    .filter-panel,
    .detail-panel,
    .surface {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(40, 44, 52, 0.96);
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.22);
    }
    .filter-panel,
    .detail-panel {
      position: sticky;
      top: 112px;
      padding: 14px;
      overflow: hidden;
    }
    .panel-title {
      margin: 0 0 10px;
      font-size: 14px;
      line-height: 1.3;
      letter-spacing: 0;
      color: var(--bright);
    }
    label {
      display: grid;
      gap: 5px;
      margin-bottom: 12px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }
    input,
    select {
      width: 100%;
      max-width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 9px;
      background: var(--page-deep);
      color: var(--ink);
      font: inherit;
      font-size: 13px;
      box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.22);
    }
    input::placeholder {
      color: var(--subtle);
    }
    input:focus,
    select:focus {
      outline: 2px solid rgba(97, 175, 239, 0.26);
      border-color: var(--blue);
    }
    .toggle-label {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      color: var(--ink);
      font-size: 13px;
      font-weight: 500;
      text-transform: none;
    }
    .toggle-label input {
      width: 16px;
      min-height: 16px;
    }
    .tool-row {
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }
    .segmented {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 4px;
      padding: 3px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--page-deep);
    }
    .seg-btn,
    .secondary-action,
    .mini-action {
      min-height: 30px;
      border: 1px solid var(--soft-line);
      border-radius: 6px;
      background: var(--panel-deep);
      color: var(--ink);
      cursor: pointer;
      font: inherit;
      font-size: 12px;
      line-height: 1.2;
      transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
    }
    .seg-btn:hover,
    .secondary-action:hover,
    .mini-action:hover,
    .filter-chip:hover {
      border-color: rgba(97, 175, 239, 0.62);
      color: var(--bright);
    }
    .seg-btn.active-density {
      border-color: rgba(97, 175, 239, 0.48);
      background: var(--blue-soft);
      color: var(--blue);
      font-weight: 750;
    }
    .secondary-action {
      width: 100%;
      padding: 7px 9px;
      text-align: center;
    }
    .filter-foot {
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid var(--soft-line);
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    .content-stack {
      display: grid;
      gap: 12px;
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 12px;
    }
    .section-head > div {
      min-width: 0;
    }
    .section-head h2 {
      margin: 0;
      font-size: 18px;
      line-height: 1.25;
      letter-spacing: 0;
      color: var(--bright);
    }
    .section-head p {
      margin: 4px 0 0;
      color: var(--muted);
      line-height: 1.45;
    }
    .repo-list,
    .card-grid,
    .panel-grid,
    .shelf-grid {
      display: grid;
      gap: 10px;
    }
    .card-grid {
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    }
    .panel-grid {
      grid-template-columns: repeat(2, minmax(280px, 1fr));
    }
    .shelf-grid {
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    }
    .repo-card,
    .experiment-card {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: linear-gradient(180deg, rgba(48, 54, 66, 0.82), rgba(40, 44, 52, 0.98));
      text-align: left;
      color: inherit;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.22);
    }
    .repo-card {
      display: grid;
      gap: 8px;
      cursor: pointer;
      transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease, background 140ms ease;
    }
    .repo-card:hover {
      border-color: rgba(97, 175, 239, 0.72);
      box-shadow: var(--shadow);
      transform: translateY(-1px);
    }
    .repo-card.selected {
      border-color: var(--blue);
      background: linear-gradient(180deg, rgba(97, 175, 239, 0.13), rgba(40, 44, 52, 0.98));
      box-shadow: inset 3px 0 0 var(--blue), 0 0 0 2px rgba(97, 175, 239, 0.18);
    }
    body[data-density="compact"] .repo-list,
    body[data-density="compact"] .card-grid {
      gap: 7px;
    }
    body[data-density="compact"] .repo-card {
      padding: 10px;
      gap: 6px;
    }
    body[data-density="compact"] .repo-card .summary-text {
      -webkit-line-clamp: 1;
    }
    .repo-top,
    .card-head,
    .detail-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
      flex-wrap: wrap;
    }
    .repo-top > div,
    .card-head > div,
    .detail-head > div {
      min-width: 0;
    }
    .repo-name,
    .card-title {
      margin-top: 3px;
      color: var(--bright);
      font-weight: 750;
      line-height: 1.3;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .repo-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }
    .repo-meta span {
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .id {
      color: var(--subtle);
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      line-height: 1.4;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .summary-text {
      color: var(--ink);
      font-size: 13px;
      line-height: 1.45;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .repo-card .summary-text {
      display: -webkit-box;
      overflow: hidden;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
    }
    .detail-panel .summary-text {
      display: -webkit-box;
      overflow: hidden;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 5;
    }
    .status {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 24px;
      min-width: 76px;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 750;
      text-align: center;
      white-space: nowrap;
      flex: 0 0 auto;
      max-width: 100%;
    }
    .accepted {
      border: 1px solid rgba(152, 195, 121, 0.5);
      background: var(--green-soft);
      color: var(--green);
    }
    .rejected {
      border: 1px solid rgba(224, 108, 117, 0.52);
      background: var(--red-soft);
      color: var(--red);
    }
    .active {
      border: 1px solid rgba(97, 175, 239, 0.5);
      background: var(--blue-soft);
      color: var(--blue);
    }
    .observed {
      border: 1px solid rgba(198, 120, 221, 0.5);
      background: var(--violet-soft);
      color: var(--violet);
    }
    .proposed {
      border: 1px solid rgba(229, 192, 123, 0.52);
      background: var(--amber-soft);
      color: var(--amber);
    }
    .unknown {
      border: 1px solid #4b5263;
      background: #2f3540;
      color: var(--muted);
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .chips.tight {
      gap: 5px;
    }
    .chips.tight .chip {
      min-height: 22px;
      padding: 2px 7px;
      font-size: 11px;
    }
    button.chip {
      font: inherit;
      cursor: pointer;
    }
    .filter-chip {
      transition: border-color 120ms ease, color 120ms ease, background 120ms ease;
    }
    .chip.source {
      border-color: #4b5263;
      background: #2f3540;
    }
    .chip.warn {
      border-color: rgba(229, 192, 123, 0.54);
      background: var(--amber-soft);
      color: var(--amber);
    }
    .chip.note {
      border-color: #4b5263;
      background: #2f3540;
      color: var(--muted);
    }
    .chip.good {
      border-color: rgba(152, 195, 121, 0.48);
      background: var(--green-soft);
      color: var(--green);
    }
    .kv-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .kv {
      min-width: 0;
      border-top: 1px solid var(--soft-line);
      padding-top: 8px;
      font-size: 13px;
      line-height: 1.35;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .kv span {
      display: block;
      margin-bottom: 2px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .score-row,
    .action-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;
      min-height: 24px;
    }
    .score-pill {
      display: inline-grid;
      grid-template-columns: auto auto;
      align-items: baseline;
      gap: 6px;
      max-width: 100%;
      min-height: 24px;
      border: 1px solid var(--soft-line);
      border-radius: 6px;
      padding: 3px 7px;
      background: var(--panel-deep);
      color: var(--ink);
      font-size: 12px;
      line-height: 1.2;
    }
    .score-pill span {
      color: var(--muted);
      font-size: 10px;
      font-weight: 750;
      text-transform: uppercase;
    }
    .score-pill strong {
      color: var(--bright);
      font-weight: 750;
      overflow-wrap: anywhere;
    }
    .score-pill.positive {
      border-color: rgba(152, 195, 121, 0.45);
      background: var(--green-soft);
    }
    .score-pill.positive strong { color: var(--green); }
    .score-pill.negative {
      border-color: rgba(224, 108, 117, 0.48);
      background: var(--red-soft);
    }
    .score-pill.negative strong { color: var(--red); }
    .mini-action {
      min-height: 24px;
      padding: 3px 7px;
    }
    .mini-action.pinned {
      border-color: rgba(229, 192, 123, 0.48);
      background: var(--amber-soft);
      color: var(--amber);
    }
    .detail-panel h2 {
      margin: 0;
      font-size: 16px;
      line-height: 1.25;
      letter-spacing: 0;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .detail-panel h3,
    .surface h3 {
      margin: 16px 0 8px;
      font-size: 13px;
      letter-spacing: 0;
    }
    details.detail-section {
      border-top: 1px solid var(--soft-line);
    }
    details.detail-section summary {
      cursor: pointer;
      color: var(--bright);
      font-size: 13px;
      font-weight: 750;
      list-style-position: inside;
    }
    .detail-section {
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid var(--soft-line);
    }
    .file-list {
      display: grid;
      gap: 5px;
      max-height: 160px;
      overflow: auto;
      color: var(--ink);
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      line-height: 1.35;
    }
    .file-list div {
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .pin-tray {
      display: grid;
      gap: 8px;
      margin-top: 12px;
      padding: 10px;
      border: 1px solid var(--soft-line);
      border-radius: 8px;
      background: var(--page-deep);
    }
    .pin-list {
      display: grid;
      gap: 6px;
    }
    .pin-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      line-height: 1.35;
    }
    .pin-row button:first-child {
      border: 0;
      padding: 0;
      background: transparent;
      color: var(--bright);
      text-align: left;
      cursor: pointer;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .surface {
      padding: 14px;
    }
    .surface h2 {
      margin: 0 0 8px;
      font-size: 16px;
      line-height: 1.3;
      letter-spacing: 0;
      color: var(--bright);
    }
    .muted {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .table-wrap {
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: auto;
      max-height: 420px;
      background: var(--panel-deep);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 680px;
    }
    th,
    td {
      border-bottom: 1px solid var(--soft-line);
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 2;
      background: var(--panel-soft);
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
    }
    tr:last-child td { border-bottom: 0; }
    .bar-row {
      display: grid;
      grid-template-columns: minmax(90px, 0.8fr) minmax(90px, 1fr) 48px;
      gap: 8px;
      align-items: center;
      margin: 7px 0;
      font-size: 12px;
    }
    .bar-label {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    button.bar-label {
      border: 0;
      padding: 0;
      background: transparent;
      color: var(--ink);
      cursor: pointer;
      text-align: left;
      font: inherit;
    }
    .bar {
      height: 9px;
      border-radius: 999px;
      background: var(--soft-line);
      overflow: hidden;
    }
    .bar span {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: var(--blue);
    }
    .collection-shelf {
      display: grid;
      gap: 10px;
      min-height: 210px;
    }
    .shelf-items {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .shelf-items .chip {
      max-width: 100%;
      white-space: normal;
    }
    .compare-grid {
      display: grid;
      gap: 12px;
    }
    .compare-board {
      display: grid;
      grid-template-columns: repeat(4, minmax(220px, 1fr));
      gap: 10px;
      align-items: stretch;
    }
    .compare-column {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--page-deep);
      padding: 10px;
    }
    .compare-column h2 {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin: 0 0 10px;
      font-size: 14px;
      line-height: 1.3;
      color: var(--bright);
      overflow-wrap: anywhere;
    }
    .compare-column h2 span {
      color: var(--muted);
      font-weight: 650;
    }
    .compare-card {
      display: grid;
      gap: 8px;
      margin-top: 8px;
      border: 1px solid var(--soft-line);
      border-left: 3px solid #4b5263;
      border-radius: 8px;
      padding: 11px;
      background: var(--panel-deep);
      overflow: hidden;
    }
    .compare-card.stage-executing { border-left-color: var(--green); }
    .compare-card.stage-forward_accumulating { border-left-color: var(--blue); }
    .compare-card.stage-replay_only { border-left-color: var(--amber); }
    .compare-card.stage-blocked { border-left-color: var(--red); }
    .compare-card h3 {
      margin: 0;
      color: var(--bright);
      font-size: 14px;
      line-height: 1.35;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .mini-stats {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 6px;
    }
    .mini-stat {
      min-width: 0;
      border: 1px solid var(--soft-line);
      border-radius: 6px;
      padding: 6px;
      background: var(--page-deep);
      color: var(--muted);
      font-size: 11px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    .mini-stat strong {
      display: block;
      margin-top: 3px;
      color: var(--bright);
      font-size: 16px;
      line-height: 1.1;
    }
    .progress-track {
      height: 8px;
      border-radius: 999px;
      background: var(--soft-line);
      overflow: hidden;
    }
    .progress-fill {
      display: block;
      height: 100%;
      width: 0%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--blue), var(--green));
    }
    .compare-note {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .curve-panel {
      display: grid;
      gap: 12px;
    }
    .chart-shell {
      min-height: 330px;
      border: 1px solid var(--soft-line);
      border-radius: 8px;
      background: var(--page-deep);
      padding: 12px;
      overflow: hidden;
    }
    .curve-chart {
      display: block;
      width: 100%;
      height: auto;
      min-height: 280px;
    }
    .axis-line,
    .grid-line {
      stroke: #3a404b;
      stroke-width: 1;
    }
    .axis-label {
      fill: var(--muted);
      font-size: 11px;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .curve-path {
      fill: none;
      stroke-width: 3;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .curve-dot {
      stroke: #252a32;
      stroke-width: 2;
    }
    .curve-legend {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 8px;
    }
    .legend-item {
      display: grid;
      grid-template-columns: 10px minmax(0, 1fr) auto;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--soft-line);
      border-radius: 8px;
      padding: 9px;
      background: var(--page-deep);
      font-size: 12px;
      line-height: 1.35;
      overflow: hidden;
    }
    .legend-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }
    .legend-name {
      color: var(--bright);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .legend-metric {
      color: var(--muted);
      white-space: nowrap;
    }
    .activation-strips {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 8px;
    }
    .activation-strip {
      min-width: 0;
      border: 1px solid var(--soft-line);
      border-radius: 8px;
      padding: 10px;
      background: var(--page-deep);
      display: grid;
      gap: 8px;
    }
    .strip-head {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: flex-start;
    }
    .strip-name {
      color: var(--bright);
      font-weight: 700;
      line-height: 1.3;
      overflow-wrap: anywhere;
    }
    details.surface summary {
      cursor: pointer;
      color: var(--bright);
      font-weight: 750;
      list-style-position: inside;
    }
    .empty {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 28px;
      background: var(--panel-deep);
      color: var(--muted);
      text-align: center;
    }
    @media (max-width: 1180px) {
      .hub-shell {
        grid-template-columns: 240px minmax(0, 1fr);
      }
      .detail-panel {
        position: static;
        grid-column: 1 / -1;
      }
    }
    @media (max-width: 820px) {
      .topbar-inner,
      main {
        padding-left: 14px;
        padding-right: 14px;
      }
      .title-row {
        display: grid;
        gap: 12px;
      }
      .meta-pills {
        display: grid;
        grid-template-columns: 1fr;
        justify-content: flex-start;
        min-width: 0;
        max-width: 100%;
      }
      .pill {
        max-width: 100%;
        justify-content: flex-start;
      }
      .tabs {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 6px;
      }
      .tab {
        width: 100%;
        padding-left: 6px;
        padding-right: 6px;
        text-align: center;
      }
      .summary {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
        padding-bottom: 4px;
      }
      .metric {
        min-width: 0;
        min-height: 64px;
        padding: 10px;
      }
      .metric .value {
        margin-top: 5px;
        font-size: 20px;
      }
      .hub-shell,
      .panel-grid,
      .compare-board,
      .shelf-grid,
      .card-grid {
        grid-template-columns: 1fr;
      }
      .section-head {
        display: grid;
      }
      .section-head .pill {
        justify-self: start;
      }
      .repo-top,
      .card-head,
      .detail-head {
        display: grid;
        grid-template-columns: 1fr;
      }
      .status {
        justify-self: start;
        white-space: normal;
      }
      .filter-panel {
        position: static;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }
      .filter-panel .panel-title,
      .filter-panel label:first-of-type,
      .tool-row,
      .filter-foot {
        grid-column: 1 / -1;
      }
      .filter-panel label {
        margin-bottom: 0;
      }
      .bar-row {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="title-row">
        <div>
          <h1>Ginger Experiment Dashboard</h1>
          <p class="subtitle">Hub-style local browser for experiment identity, evidence, and production readiness.</p>
        </div>
        <div class="meta-pills" aria-label="Dashboard metadata">
          <span class="pill">Generated <strong id="generated"></strong></span>
          <span class="pill">Next <strong id="next-id"></strong></span>
          <span class="pill">Registry <strong id="registry"></strong></span>
        </div>
      </div>
      <nav class="tabs" aria-label="Dashboard views">
        <button class="tab active-tab" data-view="experiments">Experiments</button>
        <button class="tab" data-view="cards">Cards</button>
        <button class="tab" data-view="rejected-upside">Rejected Upside</button>
        <button class="tab" data-view="leaderboards">Leaderboards</button>
        <button class="tab" data-view="dataset">Dataset View</button>
        <button class="tab" data-view="collections">Collections</button>
        <button class="tab" data-view="production">Prod Compare</button>
      </nav>
    </div>
  </header>
  <main>
    <section class="summary" id="summary"></section>
    <div class="hub-shell">
      <aside class="filter-panel" aria-label="Filters">
        <h2 class="panel-title">Discover</h2>
        <label>Search<input id="search" type="search" autocomplete="off" placeholder="ID, family, variable, note"></label>
        <label>Status<select id="status"></select></label>
        <label>Source<select id="source"></select></label>
        <label>Sort<select id="sort"></select></label>
        <label class="toggle-label"><input id="anomalies" type="checkbox"> Anomalies only</label>
        <div class="tool-row">
          <div class="segmented" aria-label="Card density">
            <button class="seg-btn active-density" type="button" data-density="comfortable">Roomy</button>
            <button class="seg-btn" type="button" data-density="compact">Compact</button>
          </div>
          <button class="secondary-action" id="reset-filters" type="button">Reset filters</button>
        </div>
        <div class="filter-foot" id="filter-foot"></div>
      </aside>
      <section class="content-stack" id="results" aria-live="polite"></section>
      <aside class="detail-panel" id="detail" aria-label="Selected experiment"></aside>
    </div>
  </main>
  <script id="experiment-data" type="application/json">__INDEX_JSON__</script>
  <script>
    const index = JSON.parse(document.getElementById("experiment-data").textContent);
    const rows = index.experiments || [];
    const searchInput = document.getElementById("search");
    const statusSelect = document.getElementById("status");
    const sourceSelect = document.getElementById("source");
    const sortSelect = document.getElementById("sort");
    const anomaliesOnly = document.getElementById("anomalies");
    const resetFiltersButton = document.getElementById("reset-filters");
    const resultsEl = document.getElementById("results");
    const detailEl = document.getElementById("detail");
    const filterFoot = document.getElementById("filter-foot");
    let activeView = "experiments";
    let selectedId = rows[0]?.experiment_id || null;
    let density = "comfortable";
    const pinnedIds = new Set();
    const sortOptions = [
      ["recent", "Recent ID"],
      ["ev_desc", "EV Delta"],
      ["pnl_desc", "PnL Delta"],
      ["anomalies_desc", "Anomalies"],
      ["status", "Status"]
    ];
    const missingMetricSortValue = -1e100;

    function text(value) {
      return value == null ? "" : String(value);
    }
    function esc(value) {
      return text(value).replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }
    function optionList(values) {
      return ["all"].concat(Array.from(new Set(values.filter(Boolean))).sort());
    }
    function fillSelect(select, values) {
      select.innerHTML = optionList(values).map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join("");
    }
    function fillSortSelect() {
      sortSelect.innerHTML = sortOptions.map(([value, label]) => (
        `<option value="${esc(value)}">${esc(label)}</option>`
      )).join("");
    }
    function statusLabel(row) {
      return row?.status_group || "unknown";
    }
    function metricValue(row, key) {
      const n = Number((row?.metrics || row?.card?.metrics || {})[key]);
      return Number.isFinite(n) ? n : null;
    }
    function sortedRows(items) {
      const sorted = items.slice();
      const mode = sortSelect.value || "recent";
      sorted.sort((a, b) => {
        if (mode === "ev_desc") {
          return (metricValue(b, "expected_value_score_delta") ?? missingMetricSortValue) - (metricValue(a, "expected_value_score_delta") ?? missingMetricSortValue);
        }
        if (mode === "pnl_desc") {
          return (metricValue(b, "total_pnl_delta") ?? missingMetricSortValue) - (metricValue(a, "total_pnl_delta") ?? missingMetricSortValue);
        }
        if (mode === "anomalies_desc") {
          return ((b.anomalies || []).length - (a.anomalies || []).length) || text(b.experiment_id).localeCompare(text(a.experiment_id));
        }
        if (mode === "status") {
          return statusLabel(a).localeCompare(statusLabel(b)) || text(b.experiment_id).localeCompare(text(a.experiment_id));
        }
        return text(b.experiment_id).localeCompare(text(a.experiment_id));
      });
      return sorted;
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
    function filteredRows() {
      const q = searchInput.value.trim().toLowerCase();
      const status = statusSelect.value;
      const source = sourceSelect.value;
      return sortedRows(rows.filter(row => {
        if (q && !rowBlob(row).includes(q)) return false;
        if (status !== "all" && statusLabel(row) !== status) return false;
        if (source !== "all" && !(row.sources || []).includes(source)) return false;
        if (anomaliesOnly.checked && !(row.anomalies || []).length) return false;
        return true;
      }));
    }
    function fmtNumber(value) {
      const n = Number(value);
      if (value == null || !Number.isFinite(n)) return "";
      if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
      return n.toLocaleString(undefined, { maximumFractionDigits: 4 });
    }
    function hasDisplayValue(value) {
      return value !== null && value !== undefined && text(value).trim() !== "";
    }
    function metrics(row) {
      return row?.metrics || row?.card?.metrics || {};
    }
    function primaryTitle(row) {
      const card = row?.card || {};
      return card.title || row?.trial_variant_id || row?.trial_family || row?.mechanism_family || row?.change_type || row?.experiment_id || "";
    }
    function primarySummary(row) {
      const card = row?.card || {};
      return card.summary || row?.summary || row?.hypothesis || "";
    }
    function chips(values, mode="") {
      const cls = mode ? ` ${mode}` : "";
      return `<div class="chips">${(values || []).map(v => `<span class="chip${cls}">${esc(v)}</span>`).join("")}</div>`;
    }
    function filterChip(label, key, value, mode="") {
      if (!hasDisplayValue(value)) return "";
      const cls = mode ? ` ${mode}` : "";
      return `<button class="chip filter-chip${cls}" type="button" data-filter-key="${esc(key)}" data-filter-value="${esc(value)}">${esc(label || value)}</button>`;
    }
    function sourceChips(values) {
      return `<div class="chips">${(values || []).map(value => filterChip(value, "source", value, "source")).join("")}</div>`;
    }
    function compactFacts(row) {
      const facts = [
        ["lane", row?.lane],
        ["query", row?.trial_family || row?.mechanism_family],
        ["query", row?.changed_variable || row?.single_causal_variable]
      ].filter(([, value]) => hasDisplayValue(value));
      return facts.slice(0, 3);
    }
    function metricTone(value) {
      const n = Number(value);
      if (!Number.isFinite(n) || n === 0) return "";
      return n > 0 ? "positive" : "negative";
    }
    function scorePill(label, value) {
      const formatted = fmtNumber(value);
      if (!formatted) return "";
      const tone = metricTone(value);
      return `<span class="score-pill ${tone}"><span>${esc(label)}</span><strong>${esc(formatted)}</strong></span>`;
    }
    function metricBlock(label, value) {
      if (!hasDisplayValue(value)) return "";
      return `<div class="kv"><span>${esc(label)}</span>${esc(value)}</div>`;
    }
    function renderSummary() {
      const s = index.summary || {};
      const metricsList = [
        ["Experiments", s.experiment_count, "tone-blue"],
        ["Registry Rows", s.registry_count, "tone-violet"],
        ["Anomalies", s.anomaly_experiment_count || 0, "tone-amber"],
        ["Identity Notes", s.identity_note_experiment_count || 0, "tone-cyan"],
        ["Accepted", (s.status_counts || {}).accepted || 0, "tone-green"],
        ["Rejected", (s.status_counts || {}).rejected || 0, "tone-red"]
      ];
      document.getElementById("summary").innerHTML = metricsList.map(([label, value, tone]) => (
        `<div class="metric ${esc(tone || "")}"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`
      )).join("");
      document.getElementById("generated").textContent = index.generated_at || "";
      document.getElementById("next-id").textContent = index.next_experiment_id || "";
      document.getElementById("registry").textContent = index.registry_path || "";
    }
    function selectedRow(matches=filteredRows()) {
      const current = rows.find(row => row.experiment_id === selectedId);
      if (current && matches.some(row => row.experiment_id === current.experiment_id)) return current;
      selectedId = matches[0]?.experiment_id || null;
      return matches[0] || null;
    }
    function renderPinnedTray() {
      const pinned = Array.from(pinnedIds)
        .map(id => rows.find(row => row.experiment_id === id))
        .filter(Boolean);
      if (!pinned.length) return "";
      const items = pinned.slice(0, 8).map(row => `
        <div class="pin-row">
          <button type="button" data-select-id="${esc(row.experiment_id)}" title="${esc(primaryTitle(row))}">${esc(row.experiment_id)} / ${esc(primaryTitle(row))}</button>
          <button class="mini-action" type="button" data-action="pin-id" data-exp-id="${esc(row.experiment_id)}">Remove</button>
        </div>`).join("");
      return `
        <div class="pin-tray">
          <div class="repo-top">
            <h3>Pinned Compare</h3>
            <span class="chip source">${esc(pinned.length)} pinned</span>
          </div>
          <div class="pin-list">${items}</div>
        </div>`;
    }
    function renderDetail(row) {
      if (!row) {
        detailEl.innerHTML = `<h2>No experiment selected</h2><p class="muted">Change filters to reveal experiments.</p>`;
        return;
      }
      const m = metrics(row);
      const meta = row.card?.metadata || {};
      const pinned = pinnedIds.has(row.experiment_id);
      const anomalySection = (row.anomalies || []).length ? `
        <div class="detail-section">
          <h3>Anomalies</h3>
          ${chips(row.anomalies, "warn")}
        </div>` : "";
      const noteSection = (row.identity_notes || []).length ? `
        <div class="detail-section">
          <h3>Identity Notes</h3>
          ${chips(row.identity_notes, "note")}
        </div>` : "";
      const followupSection = (row.accepted_followups || []).length ? `
        <div class="detail-section">
          <h3>Accepted Follow-Ups</h3>
          <div class="file-list">${row.accepted_followups.map(followup => `<div>${esc(followup.experiment_id)} / ${esc((followup.evidence || []).join(", "))}</div>`).join("")}</div>
        </div>` : "";
      const files = row.files || [];
      detailEl.innerHTML = `
        <div class="detail-head">
          <div>
            <div class="id">${esc(row.experiment_id)}</div>
            <h2>${esc(primaryTitle(row))}</h2>
          </div>
          <span class="status ${esc(statusLabel(row))}">${esc(statusLabel(row))}</span>
        </div>
        <div class="action-row">
          <button class="mini-action ${pinned ? "pinned" : ""}" type="button" data-action="pin-id" data-exp-id="${esc(row.experiment_id)}">${pinned ? "Pinned" : "Pin"}</button>
          <button class="mini-action" type="button" data-action="copy-id" data-exp-id="${esc(row.experiment_id)}">Copy ID</button>
          ${filterChip(statusLabel(row), "status", statusLabel(row), "source")}
        </div>
        <p class="summary-text">${esc(primarySummary(row))}</p>
        <div class="kv-grid">
          ${metricBlock("Lane", row.lane)}
          ${metricBlock("Trial", meta.trial_family || row.trial_family)}
          ${metricBlock("Variable", meta.changed_variable || row.changed_variable || row.single_causal_variable)}
          ${metricBlock("EV Delta", fmtNumber(m.expected_value_score_delta))}
          ${metricBlock("PnL Delta", fmtNumber(m.total_pnl_delta))}
          ${metricBlock("After EV", fmtNumber(m.after_expected_value_score))}
        </div>
        <div class="detail-section">
          <h3>Sources</h3>
          ${sourceChips(row.sources || [])}
        </div>
        ${anomalySection}
        ${noteSection}
        ${followupSection}
        <details class="detail-section">
          <summary>Files (${esc(files.length)})</summary>
          <div class="file-list">${files.slice(0, 8).map(file => `<div>${esc(file)}</div>`).join("") || `<div class="muted">No files indexed</div>`}</div>
        </details>
        ${renderPinnedTray()}`;
      bindRendered(detailEl);
    }
    function repoCard(row) {
      const m = metrics(row);
      const selected = row.experiment_id === selectedId ? " selected" : "";
      const pinned = pinnedIds.has(row.experiment_id);
      const facts = compactFacts(row);
      const summary = primarySummary(row);
      const metricPills = [
        scorePill("EV Δ", m.expected_value_score_delta),
        scorePill("After EV", m.after_expected_value_score),
        scorePill("PnL", m.total_pnl_delta)
      ].filter(Boolean).join("");
      const issuePills = [
        (row.anomalies || []).length ? `<span class="chip warn">${esc((row.anomalies || []).length)} anomalies</span>` : "",
        (row.identity_notes || []).length ? `<span class="chip note">${esc((row.identity_notes || []).length)} notes</span>` : "",
        (row.accepted_followup_ids || []).length ? `<span class="chip good">${esc((row.accepted_followup_ids || []).length)} accepted follow-up</span>` : ""
      ].filter(Boolean).join("");
      return `
        <article class="repo-card${selected}" data-select-id="${esc(row.experiment_id)}" tabindex="0">
          <div class="repo-top">
            <div>
              <div class="id">${esc(row.experiment_id)}</div>
              <div class="repo-name">${esc(primaryTitle(row))}</div>
            </div>
            <span class="status ${esc(statusLabel(row))}">${esc(statusLabel(row))}</span>
          </div>
          ${facts.length ? `<div class="repo-meta">${facts.map(([key, value]) => filterChip(value, key, value)).join("")}</div>` : ""}
          ${summary ? `<div class="summary-text">${esc(summary)}</div>` : ""}
          <div class="score-row">
            ${metricPills}
            ${issuePills ? `<div class="chips tight">${issuePills}</div>` : ""}
            <button class="mini-action ${pinned ? "pinned" : ""}" type="button" data-action="pin-id" data-exp-id="${esc(row.experiment_id)}">${pinned ? "Pinned" : "Pin"}</button>
            <button class="mini-action" type="button" data-action="copy-id" data-exp-id="${esc(row.experiment_id)}">Copy</button>
          </div>
        </article>`;
    }
    function applyFilter(key, value) {
      if (key === "status" && Array.from(statusSelect.options).some(option => option.value === value)) {
        statusSelect.value = value;
      } else if (key === "source" && Array.from(sourceSelect.options).some(option => option.value === value)) {
        sourceSelect.value = value;
      } else {
        searchInput.value = value;
      }
      renderActive();
    }
    function copyExperimentId(id) {
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(id).catch(() => {});
      }
      filterFoot.textContent = `Copied ${id}`;
    }
    function togglePin(id) {
      if (pinnedIds.has(id)) {
        pinnedIds.delete(id);
      } else {
        pinnedIds.add(id);
      }
      renderActive();
    }
    function bindSelectableCards(root=resultsEl) {
      root.querySelectorAll("[data-select-id]").forEach(card => {
        const select = () => {
          selectedId = card.dataset.selectId;
          renderActive();
        };
        card.addEventListener("click", select);
        card.addEventListener("keydown", event => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            select();
          }
        });
      });
    }
    function bindRendered(root=resultsEl) {
      bindSelectableCards(root);
      root.querySelectorAll("[data-filter-key]").forEach(button => {
        button.addEventListener("click", event => {
          event.preventDefault();
          event.stopPropagation();
          applyFilter(button.dataset.filterKey, button.dataset.filterValue);
        });
      });
      root.querySelectorAll("[data-action]").forEach(button => {
        button.addEventListener("click", event => {
          event.preventDefault();
          event.stopPropagation();
          const id = button.dataset.expId;
          if (button.dataset.action === "copy-id") copyExperimentId(id);
          if (button.dataset.action === "pin-id") togglePin(id);
        });
      });
    }
    function renderExperiments() {
      const matches = filteredRows();
      const row = selectedRow(matches);
      renderDetail(row);
      filterFoot.textContent = `${matches.length} matches from ${rows.length} indexed experiments.`;
      if (!matches.length) {
        resultsEl.innerHTML = `<div class="empty">No matching experiments</div>`;
        return;
      }
      const limit = 140;
      resultsEl.innerHTML = `
        <section class="surface">
          <div class="section-head">
            <div>
              <h2>Experiment Hub</h2>
              <p>Click tags to filter, pin rows to compare, and sort without leaving the page.</p>
            </div>
            <span class="pill">Showing <strong>${esc(Math.min(matches.length, limit))}</strong></span>
          </div>
          <div class="repo-list">${matches.slice(0, limit).map(repoCard).join("")}</div>
        </section>`;
      bindRendered();
    }
    function renderCards() {
      const matches = filteredRows();
      const row = selectedRow(matches);
      renderDetail(row);
      filterFoot.textContent = `${matches.length} matching cards.`;
      resultsEl.innerHTML = `
        <section class="surface">
          <div class="section-head">
            <div>
              <h2>Experiment Cards</h2>
              <p>Compact comparison of identity, variable, and outcome signal.</p>
            </div>
          </div>
          <div class="card-grid">${matches.slice(0, 96).map(repoCard).join("") || `<div class="empty">No cards match the filters</div>`}</div>
        </section>`;
      bindRendered();
    }
    function fullRowsForLeaderboard(items) {
      return (items || []).map(item => {
        const full = rows.find(row => row.experiment_id === item.experiment_id);
        if (!full) return item;
        return {
          ...full,
          accepted_followups: item.accepted_followups || [],
          accepted_followup_ids: item.accepted_followup_ids || [],
          has_accepted_followup: Boolean(item.has_accepted_followup),
        };
      });
    }
    function renderRejectedUpside() {
      const boards = index.leaderboards || {};
      const upsideRows = fullRowsForLeaderboard(boards.rejected_high_upside || []);
      const afterRows = fullRowsForLeaderboard(boards.rejected_high_after_ev || []);
      const unresolvedAfterRows = fullRowsForLeaderboard(boards.unresolved_rejected_high_after_ev || []);
      const resolvedAfterRows = fullRowsForLeaderboard(boards.resolved_rejected_high_after_ev || []);
      const row = selectedRow(unresolvedAfterRows.length ? unresolvedAfterRows : afterRows.length ? afterRows : upsideRows.length ? upsideRows : filteredRows());
      renderDetail(row);
      filterFoot.textContent = `${unresolvedAfterRows.length} high-after-EV rejected experiments have no accepted follow-up by conservative lineage; ${resolvedAfterRows.length} have accepted follow-ups.`;
      resultsEl.innerHTML = `
        <section class="surface">
          <div class="section-head">
            <div>
              <h2>Still Open: Rejected After EV &gt; 10</h2>
              <p>No later accepted experiment matched by explicit reference, same trial family, or same mechanism family.</p>
            </div>
            <span class="pill">Open <strong>${esc(unresolvedAfterRows.length)}</strong></span>
          </div>
          <div class="card-grid">${unresolvedAfterRows.slice(0, 80).map(repoCard).join("") || `<div class="empty">No open high-after-EV rejected experiments by the current lineage rule</div>`}</div>
        </section>
        <section class="surface">
          <div class="section-head">
            <div>
              <h2>Rejected After EV &gt; 10</h2>
              <p>All high absolute-EV failures. Cards marked with accepted follow-up can usually be deprioritized.</p>
            </div>
            <span class="pill">Above 10 <strong>${esc(afterRows.length)}</strong></span>
          </div>
          <div class="card-grid">${afterRows.slice(0, 80).map(repoCard).join("") || `<div class="empty">No rejected experiments with after EV above 10 indexed</div>`}</div>
        </section>
        <section class="surface">
          <div class="section-head">
            <div>
              <h2>Has Accepted Follow-Up</h2>
              <p>Rejected high-EV experiments with a later accepted experiment matched by conservative lineage.</p>
            </div>
            <span class="pill">Resolved <strong>${esc(resolvedAfterRows.length)}</strong></span>
          </div>
          <div class="card-grid">${resolvedAfterRows.slice(0, 80).map(repoCard).join("") || `<div class="empty">No accepted follow-ups matched yet</div>`}</div>
        </section>
        <section class="surface">
          <div class="section-head">
            <div>
              <h2>Rejected High-Upside</h2>
              <p>Failed experiments with positive EV or PnL deltas. Use these to find blockers, concentration issues, or ideas that need fresh forward evidence.</p>
            </div>
            <span class="pill">Candidates <strong>${esc(upsideRows.length)}</strong></span>
          </div>
          <div class="card-grid">${upsideRows.slice(0, 80).map(repoCard).join("") || `<div class="empty">No rejected high-upside experiments indexed</div>`}</div>
        </section>`;
      bindRendered();
    }
    function leaderboardTable(title, rows, metric) {
      const body = (rows || []).map(row => `
        <tr data-select-id="${esc(row.experiment_id)}">
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
      const row = selectedRow(filteredRows());
      renderDetail(row);
      filterFoot.textContent = "Leaderboards use generated metric deltas from the full index.";
      const boards = index.leaderboards || {};
      const familyRows = (boards.rejected_families || []).map(item => `
        <tr><td>${esc(item.family)}</td><td>${esc(item.count)}</td></tr>`).join("");
      resultsEl.innerHTML = `
        <div class="panel-grid">
          ${leaderboardTable("High After EV", boards.high_after_ev, "after_expected_value_score")}
          ${leaderboardTable("Rejected After EV > 10", boards.rejected_high_after_ev, "after_expected_value_score")}
          ${leaderboardTable("Still Open High EV Rejects", boards.unresolved_rejected_high_after_ev, "after_expected_value_score")}
          ${leaderboardTable("Resolved High EV Rejects", boards.resolved_rejected_high_after_ev, "after_expected_value_score")}
          ${leaderboardTable("Rejected High-Upside", boards.rejected_high_upside, "expected_value_score_delta")}
          ${leaderboardTable("Top EV Delta", boards.top_ev_delta, "expected_value_score_delta")}
          ${leaderboardTable("Worst EV Delta", boards.bottom_ev_delta, "expected_value_score_delta")}
          ${leaderboardTable("Top PnL Delta", boards.top_pnl_delta, "total_pnl_delta")}
          <section class="surface">
            <h2>Rejected Families</h2>
            <div class="table-wrap"><table>
              <thead><tr><th>Family</th><th>Rejected</th></tr></thead>
              <tbody>${familyRows || `<tr><td colspan="2">No rejected family counts</td></tr>`}</tbody>
            </table></div>
          </section>
        </div>`;
      bindRendered();
    }
    function renderDatasetView() {
      const row = selectedRow(filteredRows());
      renderDetail(row);
      filterFoot.textContent = "Dataset View summarizes field coverage and dominant values.";
      const columns = (index.dataset_view || {}).columns || [];
      const cards = columns.map(col => {
        const total = Math.max(1, Number(col.present || 0) + Number(col.missing || 0));
        const top = (col.top_values || []).slice(0, 5);
        return `
          <section class="surface">
            <h2>${esc(col.field)}</h2>
            <p class="muted">${esc(col.present)} present, ${esc(col.missing)} missing, ${esc(col.unique)} unique</p>
            ${top.map(item => {
              const pct = Math.round((Number(item.count || 0) / total) * 100);
              return `<div class="bar-row"><button class="bar-label" type="button" data-filter-key="query" data-filter-value="${esc(item.value)}">${esc(item.value)}</button><div class="bar"><span style="width:${pct}%"></span></div><div>${esc(item.count)}</div></div>`;
            }).join("")}
          </section>`;
      }).join("");
      resultsEl.innerHTML = `<div class="panel-grid">${cards}</div>`;
      bindRendered();
    }
    function renderCollections() {
      const row = selectedRow(filteredRows());
      renderDetail(row);
      filterFoot.textContent = "Collections are generated shelves; they do not change experiment state.";
      const collectionRows = (index.collections || []).map(collection => `
        <section class="surface collection-shelf">
          <div class="section-head">
            <div>
              <h2>${esc(collection.title)}</h2>
              <p>${esc(collection.description)}</p>
            </div>
            <span class="pill"><strong>${esc(collection.count)}</strong></span>
          </div>
          <div class="shelf-items">${(collection.experiment_ids || []).slice(0, 36).map(id => `<span class="chip source" data-select-id="${esc(id)}">${esc(id)}</span>`).join("") || `<span class="muted">No experiments in this collection</span>`}</div>
        </section>`).join("");
      resultsEl.innerHTML = `<div class="shelf-grid">${collectionRows}</div>`;
      bindRendered();
    }
    function renderProductionCompare() {
      const compare = index.production_compare || {};
      const summary = compare.summary || {};
      const live = compare.live_positions || {};
      const surfaces = compare.surfaces || [];
      const sleeves = compare.paper_sleeves || [];
      filterFoot.textContent = "Production Compare is read-only: it summarizes current_state.md, paper sleeves, pilot ledgers, and open positions.";
      detailEl.innerHTML = `
        <h2>Production Snapshot</h2>
        <div class="detail-section">
          <h3>Open Positions</h3>
          <div class="kv-grid">
            ${metricBlock("Rows", live.count)}
            ${metricBlock("Positions", live.positions_count)}
            ${metricBlock("Observations", live.observations_count)}
            ${metricBlock("As Of", live.as_of)}
          </div>
          <div class="detail-section">${chips(live.ticker_sample || [], "source")}</div>
        </div>
        <div class="detail-section">
          <h3>Generated From</h3>
          ${chips(compare.generated_from || [], "note")}
        </div>`;
      const metricCards = [
        ["Executing", summary.executing_count || 0],
        ["Forward", summary.forward_accumulating_count || 0],
        ["Replay", summary.replay_only_count || 0],
        ["Blocked", summary.blocked_count || 0],
        ["Paper Open", summary.paper_open_count || 0],
        ["Paper Pending", summary.paper_pending_count || 0],
        ["Closed Evidence", summary.paper_closed_count || 0],
        ["Known Gaps", summary.known_gap_count || 0]
      ].map(([label, value]) => `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`).join("");
      function surfaceCard(surface) {
        const required = Number(surface.required_closed_forward || 0);
        const closed = Number(surface.paper_closed_count || 0);
        const pct = required ? Math.max(0, Math.min(100, Math.round((closed / required) * 100))) : 0;
        const progress = required ? `
          <div class="progress-track" title="${esc(closed)} / ${esc(required)} closed outcomes">
            <span class="progress-fill" style="width:${pct}%"></span>
          </div>
          <div class="compare-note">${esc(closed)} / ${esc(required)} closed outcomes / ${esc(surface.target_basis || "")}</div>` : "";
        return `
          <article class="compare-card stage-${esc(surface.state || "unknown")}">
            <div class="repo-top">
              <h3>${esc(surface.surface)}</h3>
              <span class="chip source">${esc(surface.stage_label || surface.state || "unknown")}</span>
            </div>
            <div class="compare-note">${esc(surface.default_execution_status || "")}</div>
            <div class="mini-stats">
              <div class="mini-stat">open<strong>${esc(surface.paper_open_count || 0)}</strong></div>
              <div class="mini-stat">pending<strong>${esc(surface.paper_pending_count || 0)}</strong></div>
              <div class="mini-stat">closed<strong>${esc(surface.paper_closed_count || 0)}</strong></div>
            </div>
            ${progress}
            <div class="summary-text">${esc(surface.gap_label || "")}</div>
            <div class="compare-note">${esc(surface.current_evidence || "")}</div>
            ${(surface.ticker_sample || []).length ? chips(surface.ticker_sample, "source") : ""}
          </article>`;
      }
      const stages = [
        ["executing", "Executing Now"],
        ["forward_accumulating", "Forward Accumulation"],
        ["replay_only", "Replay / Default-Off"],
        ["blocked", "Blocked / Needs Adapter"]
      ];
      const board = stages.map(([stage, title]) => {
        const items = surfaces.filter(surface => surface.state === stage);
        return `
          <section class="compare-column">
            <h2>${esc(title)} <span>${esc(items.length)}</span></h2>
            ${items.map(surfaceCard).join("") || `<div class="compare-note">No surfaces in this stage.</div>`}
          </section>`;
      }).join("");
      const sleeveRows = sleeves.map(sleeve => `
        <tr>
          <td>${esc(sleeve.sleeve || sleeve.slug)}</td>
          <td>${esc(sleeve.updated_at || "")}</td>
          <td>${esc(sleeve.open_count || 0)}</td>
          <td>${esc(sleeve.pending_count || 0)}</td>
          <td>${esc(sleeve.closed_count || 0)}</td>
          <td>${esc(sleeve.ledger_row_count ?? "")}</td>
          <td>${esc((sleeve.ticker_sample || []).join(", "))}</td>
        </tr>`).join("");
      resultsEl.innerHTML = `
        <div class="compare-grid">
          <section class="summary">${metricCards}</section>
          <section class="surface">
            <div class="section-head">
              <div>
                <h2>Production vs Backtest Activation Map</h2>
                <p>Which surfaces are live, which are only accumulating forward evidence, and what still blocks activation.</p>
              </div>
              <span class="pill">Known gaps <strong>${esc(summary.known_gap_count || 0)}</strong></span>
            </div>
            <div class="compare-board">${board}</div>
          </section>
          <section class="surface">
            <div class="section-head">
              <div>
                <h2>Paper Sleeve Ledger</h2>
                <p>Forward/paper files currently feeding the compare view.</p>
              </div>
              <span class="pill">Sleeves <strong>${esc(sleeves.length)}</strong></span>
            </div>
            <div class="table-wrap"><table>
              <thead><tr><th>Sleeve</th><th>Updated</th><th>Open</th><th>Pending</th><th>Closed</th><th>Ledger Rows</th><th>Tickers</th></tr></thead>
              <tbody>${sleeveRows || `<tr><td colspan="7">No paper sleeve states indexed</td></tr>`}</tbody>
            </table></div>
          </section>
        </div>`;
    }
    function shortSleeveName(value) {
      return text(value)
        .replace(/_PAPER$/i, "")
        .replace(/_/g, " ")
        .replace(/\\s+/g, " ")
        .trim();
    }
    function curveColor(index) {
      return ["#61afef", "#98c379", "#e5c07b", "#c678dd", "#56b6c2", "#e06c75", "#d19a66", "#abb2bf"][index % 8];
    }
    function renderEvidenceChart(curves) {
      const visible = (curves || [])
        .filter(curve => (curve.points || []).length && curve.target_count)
        .slice(0, 8);
      if (!visible.length) {
        return `<div class="empty">No forward evidence curves yet</div>`;
      }
      const width = 900;
      const height = 320;
      const left = 54;
      const right = 20;
      const top = 22;
      const bottom = 62;
      const chartWidth = width - left - right;
      const chartHeight = height - top - bottom;
      const y = value => top + (100 - Math.max(0, Math.min(100, Number(value || 0)))) / 100 * chartHeight;
      const datedPoints = visible.flatMap(curve => (curve.points || [])
        .map(point => ({ point, time: Date.parse(point.date || "") }))
        .filter(item => Number.isFinite(item.time)));
      const minTime = Math.min(...datedPoints.map(item => item.time));
      const maxTime = Math.max(...datedPoints.map(item => item.time));
      const xForTime = time => left + (maxTime === minTime ? chartWidth : ((time - minTime) / (maxTime - minTime)) * chartWidth);
      const formatDate = time => new Date(time).toISOString().slice(5, 10);
      const xTicks = maxTime === minTime
        ? [minTime]
        : [minTime, minTime + (maxTime - minTime) / 2, maxTime];
      const grid = [0, 25, 50, 75, 100].map(value => `
        <line class="grid-line" x1="${left}" y1="${y(value)}" x2="${width - right}" y2="${y(value)}"></line>
        <text class="axis-label" x="12" y="${y(value) + 4}">${value}%</text>`).join("");
      const xAxisTicks = xTicks.map(time => `
        <line class="grid-line" x1="${xForTime(time)}" y1="${top}" x2="${xForTime(time)}" y2="${height - bottom}"></line>
        <text class="axis-label" x="${xForTime(time) - 18}" y="${height - 34}">${formatDate(time)}</text>`).join("");
      const paths = visible.map((curve, curveIndex) => {
        const points = (curve.points || [])
          .map(point => ({ point, time: Date.parse(point.date || "") }))
          .filter(item => Number.isFinite(item.time));
        if (!points.length) return "";
        const color = curveColor(curveIndex);
        const coords = points.map(item => [xForTime(item.time), y(item.point.pipeline_pct)]);
        const path = coords.map(([x, y], idx) => `${idx ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
        const last = coords[coords.length - 1];
        const lastPoint = points[points.length - 1].point;
        return `
          <path class="curve-path" d="${path}" stroke="${color}"><title>${esc(curve.sleeve)} ${esc(lastPoint.date)}: ${esc(Math.round(lastPoint.pipeline_pct || 0))}% maturity, ${esc(lastPoint.closed_count || 0)} closed</title></path>
          <circle class="curve-dot" cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="4.5" fill="${color}"></circle>`;
      }).join("");
      const legend = visible.map((curve, curveIndex) => `
        <div class="legend-item">
          <span class="legend-dot" style="background:${curveColor(curveIndex)}"></span>
          <span class="legend-name" title="${esc(curve.sleeve)}">${esc(shortSleeveName(curve.sleeve))}</span>
          <span class="legend-metric">${esc(curve.latest_date || "")} / ${esc(Math.round(curve.pipeline_pct || 0))}%</span>
        </div>`).join("");
      return `
        <div class="chart-shell">
          <svg class="curve-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Forward evidence curves">
            ${grid}
            ${xAxisTicks}
            <line class="axis-line" x1="${left}" y1="${height - bottom}" x2="${width - right}" y2="${height - bottom}"></line>
            <line class="axis-line" x1="${left}" y1="${top}" x2="${left}" y2="${height - bottom}"></line>
            ${paths}
            <text class="axis-label" x="${left}" y="${height - 12}">snapshot date from paper sleeve snapshots.jsonl</text>
          </svg>
        </div>
        <div class="curve-legend">${legend}</div>`;
    }
    function activationStrip(surface) {
      const required = Number(surface.required_closed_forward || 0);
      const closed = Number(surface.paper_closed_count || 0);
      const pct = required ? Math.max(0, Math.min(100, Math.round((closed / required) * 100))) : null;
      const progress = required ? `
        <div class="progress-track" title="${esc(closed)} / ${esc(required)} closed outcomes">
          <span class="progress-fill" style="width:${pct}%"></span>
        </div>` : "";
      return `
        <article class="activation-strip">
          <div class="strip-head">
            <div class="strip-name">${esc(surface.surface)}</div>
            <span class="chip source">${esc(surface.stage_label || surface.state || "unknown")}</span>
          </div>
          ${progress}
          <div class="compare-note">${required ? `${esc(closed)} / ${esc(required)} closed, ${esc(surface.evidence_gap || 0)} remaining` : esc(surface.gap_label || "")}</div>
        </article>`;
    }
    function renderProductionCompareVisual() {
      const compare = index.production_compare || {};
      const summary = compare.summary || {};
      const live = compare.live_positions || {};
      const surfaces = compare.surfaces || [];
      const sleeves = compare.paper_sleeves || [];
      const curves = compare.evidence_curves || [];
      filterFoot.textContent = "Production Compare is read-only. The curve uses paper snapshot history; only closed outcomes count for promotion.";
      detailEl.innerHTML = `
        <h2>Production Snapshot</h2>
        <div class="detail-section">
          <h3>Open Positions</h3>
          <div class="kv-grid">
            ${metricBlock("Rows", live.count)}
            ${metricBlock("Positions", live.positions_count)}
            ${metricBlock("Observations", live.observations_count)}
            ${metricBlock("As Of", live.as_of)}
          </div>
          <div class="detail-section">${chips(live.ticker_sample || [], "source")}</div>
        </div>
        <div class="detail-section">
          <h3>Generated From</h3>
          ${chips(compare.generated_from || [], "note")}
        </div>`;
      const metricCards = [
        ["Executing", summary.executing_count || 0],
        ["Forward", summary.forward_accumulating_count || 0],
        ["Blocked", summary.blocked_count || 0],
        ["Paper Open", summary.paper_open_count || 0],
        ["Paper Pending", summary.paper_pending_count || 0],
        ["Closed", summary.paper_closed_count || 0]
      ].map(([label, value]) => `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>`).join("");
      const stages = [
        ["executing", "Executing Now"],
        ["forward_accumulating", "Forward Accumulation"],
        ["replay_only", "Replay / Default-Off"],
        ["blocked", "Blocked / Needs Adapter"]
      ];
      function surfaceCard(surface) {
        return `<article class="compare-card stage-${esc(surface.state || "unknown")}">
          <div class="repo-top">
            <h3>${esc(surface.surface)}</h3>
            <span class="chip source">${esc(surface.stage_label || surface.state || "unknown")}</span>
          </div>
          <div class="mini-stats">
            <div class="mini-stat">open<strong>${esc(surface.paper_open_count || 0)}</strong></div>
            <div class="mini-stat">pending<strong>${esc(surface.paper_pending_count || 0)}</strong></div>
            <div class="mini-stat">closed<strong>${esc(surface.paper_closed_count || 0)}</strong></div>
          </div>
          <div class="summary-text">${esc(surface.gap_label || "")}</div>
        </article>`;
      }
      const board = stages.map(([stage, title]) => {
        const items = surfaces.filter(surface => surface.state === stage);
        return `<section class="compare-column"><h2>${esc(title)} <span>${esc(items.length)}</span></h2>${items.map(surfaceCard).join("") || `<div class="compare-note">No surfaces in this stage.</div>`}</section>`;
      }).join("");
      const sleeveRows = sleeves.map(sleeve => `
        <tr>
          <td>${esc(sleeve.sleeve || sleeve.slug)}</td>
          <td>${esc(sleeve.updated_at || "")}</td>
          <td>${esc(sleeve.open_count || 0)}</td>
          <td>${esc(sleeve.pending_count || 0)}</td>
          <td>${esc(sleeve.closed_count || 0)}</td>
          <td>${esc(sleeve.forward_target_count ?? "")}</td>
          <td>${esc((sleeve.ticker_sample || []).join(", "))}</td>
        </tr>`).join("");
      resultsEl.innerHTML = `
        <div class="compare-grid">
          <section class="summary">${metricCards}</section>
          <section class="surface curve-panel">
            <div class="section-head">
              <div>
                <h2>Forward Evidence Curves</h2>
                <p>HF-style training-curve view for paper sleeves. X-axis is snapshot date; Y-axis is evidence maturity. Closed samples remain the promotion gate.</p>
              </div>
              <span class="pill">Curves <strong>${esc(curves.length)}</strong></span>
            </div>
            ${renderEvidenceChart(curves)}
          </section>
          <section class="surface">
            <div class="section-head">
              <div>
                <h2>Activation Progress</h2>
                <p>Compact closed-sample progress for the main production/backtest surfaces.</p>
              </div>
              <span class="pill">Known gaps <strong>${esc(summary.known_gap_count || 0)}</strong></span>
            </div>
            <div class="activation-strips">${surfaces.map(activationStrip).join("")}</div>
          </section>
          <details class="surface">
            <summary>Activation Map Details</summary>
            <div class="compare-board">${board}</div>
          </details>
          <details class="surface">
            <summary>Paper Sleeve Ledger</summary>
            <div class="table-wrap"><table>
              <thead><tr><th>Sleeve</th><th>Updated</th><th>Open</th><th>Pending</th><th>Closed</th><th>Target</th><th>Tickers</th></tr></thead>
              <tbody>${sleeveRows || `<tr><td colspan="7">No paper sleeve states indexed</td></tr>`}</tbody>
            </table></div>
          </details>
        </div>`;
    }
    function renderActive() {
      if (activeView === "cards") return renderCards();
      if (activeView === "rejected-upside") return renderRejectedUpside();
      if (activeView === "leaderboards") return renderLeaderboards();
      if (activeView === "dataset") return renderDatasetView();
      if (activeView === "collections") return renderCollections();
      if (activeView === "production") return renderProductionCompareVisual();
      return renderExperiments();
    }

    fillSelect(statusSelect, rows.map(statusLabel));
    fillSelect(sourceSelect, rows.flatMap(row => row.sources || []));
    fillSortSelect();
    document.body.dataset.density = density;
    renderSummary();
    renderActive();
    document.querySelectorAll(".tab").forEach(tab => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(other => other.classList.remove("active-tab"));
        tab.classList.add("active-tab");
        activeView = tab.dataset.view;
        renderActive();
      });
    });
    document.querySelectorAll("[data-density]").forEach(button => {
      button.addEventListener("click", () => {
        density = button.dataset.density;
        document.body.dataset.density = density;
        document.querySelectorAll("[data-density]").forEach(other => other.classList.toggle("active-density", other === button));
      });
    });
    resetFiltersButton.addEventListener("click", () => {
      searchInput.value = "";
      statusSelect.value = "all";
      sourceSelect.value = "all";
      sortSelect.value = "recent";
      anomaliesOnly.checked = false;
      renderActive();
    });
    [searchInput, statusSelect, sourceSelect, sortSelect, anomaliesOnly].forEach(el => {
      el.addEventListener("input", renderActive);
      el.addEventListener("change", renderActive);
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
