"""Standard paper-sleeve surfaces for observe-only watch sleeves.

exp-20260612-017: platform_rs20_no_gap, sec_10k_liquidity and space_catalyst
persist only nonstandard forward_watch/summary surfaces, so any tooling that
reads the standard ``data/paper_sleeves/<name>/{state.json, snapshots.jsonl}``
contract skips them. This module writes those standard surfaces alongside the
sleeves' internal ledgers.

These are watch/observation sleeves, not paper-trade sleeves: there are no
positions and no PnL, and this module deliberately does NOT fabricate trade
semantics. ``open_positions``/``closed_positions`` stay empty, counts stay
zero, and ``surface_kind`` marks the rows as observe-only so attribution
tooling can tell them apart from paper-trade sleeves.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from data_paths import atomic_write_json
except ImportError:  # pragma: no cover - package-style imports for tests
    from quant.data_paths import atomic_write_json


STANDARD_SURFACE_SCHEMA_VERSION = 1
SURFACE_KIND_OBSERVE_ONLY = "observe_only_watch"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _last_snapshot_asof(snapshot_path: Path) -> str | None:
    if not snapshot_path.exists():
        return None
    last: str | None = None
    try:
        with snapshot_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and row.get("asof_date"):
                    last = str(row["asof_date"])[:10]
    except OSError:
        return None
    return last


def write_standard_sleeve_surfaces(
    *,
    sleeve_dir: Path | str,
    sleeve_name: str,
    rule_version: str,
    asof_date: Any,
    pending_entries: list[dict[str, Any]] | None = None,
    extra_snapshot_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write/refresh ``state.json`` and append a daily ``snapshots.jsonl`` row.

    Idempotent per ``asof_date``: re-running for the same date refreshes
    ``state.json`` but does not append a duplicate snapshot row.
    """
    date10 = str(asof_date or "")[:10]
    if not date10:
        return {"written": False, "reason": "missing_asof_date"}

    directory = Path(sleeve_dir)
    directory.mkdir(parents=True, exist_ok=True)
    state_path = directory / "state.json"
    snapshots_path = directory / "snapshots.jsonl"
    pending = [row for row in (pending_entries or []) if isinstance(row, dict)]
    now = _utc_now_iso()

    state = {
        "schema_version": STANDARD_SURFACE_SCHEMA_VERSION,
        "sleeve": sleeve_name,
        "rule_version": rule_version,
        "surface_kind": SURFACE_KIND_OBSERVE_ONLY,
        "updated_at": now,
        "asof_date": date10,
        "trade_enabled": False,
        "pending_entries": pending,
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }
    atomic_write_json(state, state_path)

    appended = False
    if _last_snapshot_asof(snapshots_path) != date10:
        row = {
            "schema_version": STANDARD_SURFACE_SCHEMA_VERSION,
            "sleeve": sleeve_name,
            "rule_version": rule_version,
            "surface_kind": SURFACE_KIND_OBSERVE_ONLY,
            "asof_date": date10,
            "generated_at": now,
            "trade_enabled": False,
            "candidate_count": len(pending),
            "pending_count": len(pending),
            "open_position_count": 0,
            "closed_position_count": 0,
            "closed_count_today": 0,
        }
        for key, value in (extra_snapshot_fields or {}).items():
            row.setdefault(key, value)
        with snapshots_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        appended = True

    return {
        "written": True,
        "appended_snapshot": appended,
        "state_path": str(state_path),
        "snapshots_path": str(snapshots_path),
        "asof_date": date10,
        "pending_count": len(pending),
    }
