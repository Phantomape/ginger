"""Intraday structured-news event observation artifacts.

This module persists the read-only structured event contract accepted in
exp-20260630-013 from the intraday production artifact path. It writes
observation rows for later attribution only; it does not alter prompts,
signals, ranking, sizing, exits, or orders.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from data_paths import DATA_ROOT
from intraday_news_structured_events import (
    FORWARD_OBSERVATION_RULE_VERSION,
    STRUCTURED_EVENT_RULE_VERSION,
    build_forward_observation_contract,
    build_structured_event_ledger,
    safe,
)


INTRADAY_STRUCTURED_OBSERVER_RULE_VERSION = (
    "intraday_news_structured_event_snapshot_v1"
)


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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def intraday_structured_event_artifact_path(
    kind: str,
    date: str,
    time_label: str,
    data_dir: str | Path | None = None,
) -> Path:
    date_tag, _ = _date_parts(date)
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    structured_root = root / "daily" / "intraday" / "structured"
    if kind == "events":
        return (
            structured_root
            / f"intraday_news_structured_events_{date_tag}_{time_label}.json"
        )
    if kind == "observations":
        return (
            structured_root
            / f"intraday_news_structured_event_observations_{date_tag}_{time_label}.jsonl"
        )
    raise KeyError(f"unknown intraday structured artifact kind: {kind!r}")


def build_intraday_structured_event_snapshot(
    date: str,
    time_label: str,
    *,
    data_dir: str | Path | None = None,
    require_explicit_ticker_text: bool = True,
) -> dict[str, Any]:
    """Build an intraday structured event snapshot without writing it."""
    date_tag, iso_date = _date_parts(date)
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    intraday_root = root / "daily" / "intraday"
    repo_root = _repo_root_for(root)
    event_contract = build_structured_event_ledger(
        intraday_root,
        repo_root=repo_root,
        start_date=iso_date,
        end_date=iso_date,
        require_explicit_ticker_text=require_explicit_ticker_text,
    )
    event_rows = [
        row
        for row in event_contract["rows"]
        if row.get("capture_date") == iso_date and row.get("time_label") == time_label
    ]
    observation_contract = build_forward_observation_contract(event_rows)
    observation_rows = list(observation_contract["rows"])
    event_path = intraday_structured_event_artifact_path(
        "events",
        date_tag,
        time_label,
        root,
    )
    observation_path = intraday_structured_event_artifact_path(
        "observations",
        date_tag,
        time_label,
        root,
    )
    return {
        "rule_version": INTRADAY_STRUCTURED_OBSERVER_RULE_VERSION,
        "date": iso_date,
        "date_tag": date_tag,
        "time_label": time_label,
        "source_event_rule_version": STRUCTURED_EVENT_RULE_VERSION,
        "forward_observation_rule_version": FORWARD_OBSERVATION_RULE_VERSION,
        "source_kind": "intraday_trade_news",
        "event_artifact_path": str(event_path),
        "forward_observation_artifact_path": str(observation_path),
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "event_contract_audit": {
            **event_contract["audit"],
            "selected_capture_date": iso_date,
            "selected_time_label": time_label,
            "selected_ledger_rows": len(event_rows),
        },
        "forward_observation_contract_audit": observation_contract["audit"],
        "rows": event_rows,
        "forward_observations": observation_rows,
    }


def persist_intraday_structured_event_snapshot(
    date: str,
    time_label: str,
    *,
    data_dir: str | Path | None = None,
    require_explicit_ticker_text: bool = True,
) -> dict[str, Any]:
    """Write intraday structured event JSON and forward observation JSONL."""
    snapshot = build_intraday_structured_event_snapshot(
        date,
        time_label,
        data_dir=data_dir,
        require_explicit_ticker_text=require_explicit_ticker_text,
    )
    event_path = Path(snapshot["event_artifact_path"])
    observation_path = Path(snapshot["forward_observation_artifact_path"])
    event_payload = {
        key: value
        for key, value in snapshot.items()
        if key != "forward_observations"
    }
    _write_json(event_path, event_payload)
    _write_text(observation_path, _jsonl_text(snapshot["forward_observations"]))
    return {
        key: value
        for key, value in snapshot.items()
        if key not in {"rows", "forward_observations"}
    }
