"""Daily structured-news event observation artifacts.

This module persists the read-only structured event contract accepted in
exp-20260630-006 from the daily production artifact path. It writes observation
rows for later attribution only; it does not alter prompts, signals, ranking,
sizing, exits, or orders.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from daily_news_structured_events import (
    FORWARD_OBSERVATION_RULE_VERSION,
    STRUCTURED_EVENT_RULE_VERSION,
    build_forward_observation_contract,
    build_structured_event_ledger,
    safe,
)
from data_paths import DATA_ROOT, atomic_write_json, atomic_write_text, daily_artifact_path


DAILY_STRUCTURED_OBSERVER_RULE_VERSION = (
    "daily_news_structured_event_daily_snapshot_v1"
)
DEFAULT_KINDS = ("clean_trade_news",)


def _date_parts(date: str) -> tuple[str, str]:
    raw = str(date).strip()
    if re.match(r"^\d{8}$", raw):
        return raw, f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw.replace("-", ""), raw
    raise ValueError(f"date must be YYYYMMDD or YYYY-MM-DD, got {date!r}")


def _repo_root_for(data_dir: Path) -> Path:
    if data_dir.name == "data":
        return data_dir.parent
    return data_dir


def _jsonl_text(rows: Iterable[Mapping[str, Any]]) -> str:
    return "".join(
        json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n"
        for row in rows
    )


def build_daily_structured_event_snapshot(
    date: str,
    *,
    data_dir: str | Path | None = None,
    kinds: Iterable[str] = DEFAULT_KINDS,
    require_explicit_ticker_text: bool = True,
) -> dict[str, Any]:
    """Build a daily structured event snapshot without writing it."""
    date_tag, iso_date = _date_parts(date)
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    news_root = root / "daily" / "news"
    repo_root = _repo_root_for(root)
    event_contract = build_structured_event_ledger(
        news_root,
        repo_root=repo_root,
        kinds=kinds,
        start_date=iso_date,
        end_date=iso_date,
        require_explicit_ticker_text=require_explicit_ticker_text,
    )
    event_rows = list(event_contract["rows"])
    observation_contract = build_forward_observation_contract(event_rows)
    observation_rows = list(observation_contract["rows"])
    event_path = daily_artifact_path("daily_news_structured_events", date_tag, root)
    observation_path = daily_artifact_path(
        "daily_news_structured_event_observations",
        date_tag,
        root,
    )
    return {
        "rule_version": DAILY_STRUCTURED_OBSERVER_RULE_VERSION,
        "date": iso_date,
        "date_tag": date_tag,
        "source_event_rule_version": STRUCTURED_EVENT_RULE_VERSION,
        "forward_observation_rule_version": FORWARD_OBSERVATION_RULE_VERSION,
        "source_kinds": list(kinds),
        "event_artifact_path": str(event_path),
        "forward_observation_artifact_path": str(observation_path),
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "event_contract_audit": event_contract["audit"],
        "forward_observation_contract_audit": observation_contract["audit"],
        "rows": event_rows,
        "forward_observations": observation_rows,
    }


def persist_daily_structured_event_snapshot(
    date: str,
    *,
    data_dir: str | Path | None = None,
    kinds: Iterable[str] = DEFAULT_KINDS,
    require_explicit_ticker_text: bool = True,
) -> dict[str, Any]:
    """Write daily structured event JSON and forward observation JSONL."""
    snapshot = build_daily_structured_event_snapshot(
        date,
        data_dir=data_dir,
        kinds=kinds,
        require_explicit_ticker_text=require_explicit_ticker_text,
    )
    event_path = Path(snapshot["event_artifact_path"])
    observation_path = Path(snapshot["forward_observation_artifact_path"])
    event_payload = {
        key: value
        for key, value in snapshot.items()
        if key != "forward_observations"
    }
    atomic_write_json(event_payload, event_path, ensure_ascii=True, default=str)
    atomic_write_text(_jsonl_text(snapshot["forward_observations"]), observation_path)
    return {
        key: value
        for key, value in snapshot.items()
        if key not in {"rows", "forward_observations"}
    }
