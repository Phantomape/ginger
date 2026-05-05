"""Default-off external event sleeve bundle attribution.

This module aggregates the existing default-off Form 4, SEC negative-reaction,
and SEC governance/procedural paper sleeves into one production-visible bundle.
It is an attribution surface only: it does not emit orders, change core
ranking, size positions, or consume A/B slots.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


SLEEVE_NAME = "DEFAULT_OFF_EVENT_OVERLAY_BUNDLE_PAPER"
STATE_SCHEMA_VERSION = 1

SOURCE_ORDER = (
    ("form4_meaningful_purchase", "Form 4 meaningful purchase"),
    ("sec_negative_reaction", "SEC negative reaction"),
    ("sec_governance_procedural", "SEC governance/procedural"),
)

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "event_notional_usd": 10_000.0,
    "per_source_max_positions": 1,
    "source_names": [source for source, _ in SOURCE_ORDER],
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_event_sleeve_bundle_snapshot(
    *,
    as_of: str,
    form4_event_sleeve: dict[str, Any] | None = None,
    sec_negative_event_sleeve: dict[str, Any] | None = None,
    sec_governance_event_sleeve: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False

    raw_sources = {
        "form4_meaningful_purchase": form4_event_sleeve,
        "sec_negative_reaction": sec_negative_event_sleeve,
        "sec_governance_procedural": sec_governance_event_sleeve,
    }
    source_summaries = {}
    open_positions = []
    closed_positions_today = []
    new_pending_entries = []
    skipped_entries_today = []

    for source, label in SOURCE_ORDER:
        summary = _summarize_source(source, label, raw_sources.get(source))
        source_summaries[source] = summary
        open_positions.extend(
            _tag_rows(source, raw_sources.get(source), "open_positions")
        )
        closed_positions_today.extend(
            _tag_rows(source, raw_sources.get(source), "closed_positions_today")
        )
        new_pending_entries.extend(
            _tag_rows(source, raw_sources.get(source), "new_pending_entries")
        )
        skipped_entries_today.extend(
            _tag_rows(source, raw_sources.get(source), "skipped_entries_today")
        )

    totals = _aggregate_totals(source_summaries)
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "asof_date": str(as_of)[:10],
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
        "source_count": len(SOURCE_ORDER),
        "sources_with_open_positions": sum(
            1 for row in source_summaries.values() if row["open_position_count"] > 0
        ),
        "sources_with_closed_positions": sum(
            1 for row in source_summaries.values() if row["closed_position_count"] > 0
        ),
        "candidate_count": totals["candidate_count"],
        "new_pending_count": totals["new_pending_count"],
        "filled_count": totals["filled_count"],
        "closed_count_today": totals["closed_count_today"],
        "skipped_count_today": totals["skipped_count_today"],
        "pending_count": totals["pending_count"],
        "open_position_count": totals["open_position_count"],
        "closed_position_count": totals["closed_position_count"],
        "realized_pnl_to_date": totals["realized_pnl_to_date"],
        "unrealized_pnl": totals["unrealized_pnl"],
        "source_summaries": source_summaries,
        "open_positions": open_positions,
        "closed_positions_today": closed_positions_today,
        "new_pending_entries": new_pending_entries,
        "skipped_entries_today": skipped_entries_today,
        "parameters": dict(cfg),
        "production_impact": _production_impact(),
        "next_action": (
            "accumulate_closed_forward_paper_outcomes_before_trade_enabled_adapter"
        ),
    }


def empty_event_sleeve_bundle_snapshot(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "asof_date": str(as_of)[:10],
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "source_summaries": {},
        "production_impact": _production_impact(),
        "error": reason,
    }


def _summarize_source(
    source: str,
    label: str,
    snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {
            "source": source,
            "label": label,
            "available": False,
            "paper_enabled": False,
            "trade_enabled": False,
            "candidate_count": 0,
            "new_pending_count": 0,
            "filled_count": 0,
            "closed_count_today": 0,
            "skipped_count_today": 0,
            "pending_count": 0,
            "open_position_count": 0,
            "closed_position_count": 0,
            "realized_pnl_to_date": 0.0,
            "unrealized_pnl": 0.0,
            "status": "missing_snapshot",
        }
    return {
        "source": source,
        "label": label,
        "available": True,
        "paper_enabled": bool(snapshot.get("paper_enabled", False)),
        "trade_enabled": False,
        "candidate_count": _int(snapshot.get("candidate_count")),
        "new_pending_count": _int(snapshot.get("new_pending_count")),
        "filled_count": _int(snapshot.get("filled_count")),
        "closed_count_today": _int(snapshot.get("closed_count_today")),
        "skipped_count_today": _int(snapshot.get("skipped_count_today")),
        "pending_count": _int(snapshot.get("pending_count")),
        "open_position_count": _int(snapshot.get("open_position_count")),
        "closed_position_count": _int(snapshot.get("closed_position_count")),
        "realized_pnl_to_date": _money(snapshot.get("realized_pnl_to_date")),
        "unrealized_pnl": _money(snapshot.get("unrealized_pnl")),
        "status": snapshot.get("error") or "loaded",
    }


def _aggregate_totals(summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    int_keys = (
        "candidate_count",
        "new_pending_count",
        "filled_count",
        "closed_count_today",
        "skipped_count_today",
        "pending_count",
        "open_position_count",
        "closed_position_count",
    )
    totals = {key: sum(row[key] for row in summaries.values()) for key in int_keys}
    totals["realized_pnl_to_date"] = round(
        sum(row["realized_pnl_to_date"] for row in summaries.values()),
        2,
    )
    totals["unrealized_pnl"] = round(
        sum(row["unrealized_pnl"] for row in summaries.values()),
        2,
    )
    return totals


def _tag_rows(
    source: str,
    snapshot: dict[str, Any] | None,
    key: str,
) -> list[dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return []
    rows = []
    for row in snapshot.get(key) or []:
        if isinstance(row, dict):
            tagged = deepcopy(row)
            tagged.setdefault("source", source)
            rows.append(tagged)
    return rows


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _money(value: Any) -> float:
    try:
        return round(float(value or 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
        "parity_test_added": True,
        "replay_only": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_orders": False,
        "scope": "default_off_event_overlay_bundle_paper_attribution",
    }
