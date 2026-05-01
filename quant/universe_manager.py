"""Point-in-time universe registry and event-ledger helpers.

This module is the point-in-time governance source for universe expansion. Core
membership still follows the legacy watchlist, while approved pilot records can
be consumed by the real-money pilot sleeve without becoming core candidates.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "data" / "universe_registry.json"
DEFAULT_EVENTS_PATH = REPO_ROOT / "data" / "universe_events.jsonl"

VALID_STATUSES = {
    "research",
    "pilot",
    "limited_production",
    "core",
    "specialist",
    "quarantine",
    "retired",
}

TRADEABLE_STATUSES = {"pilot", "limited_production", "core"}

REQUIRED_RECORD_FIELDS = {
    "ticker",
    "status",
    "theme",
    "discovered_as_of",
    "eligible_as_of",
    "first_trade_allowed_as_of",
    "status_effective_as_of",
    "decision_as_of",
    "data_available_as_of",
    "rule_version",
    "source",
    "history_class",
    "liquidity_tier",
    "max_capital_scalar",
    "max_risk_scalar",
    "requires_event_guard",
    "event_guard_profile",
    "created_by",
    "last_reviewed_at",
}


def _parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value)
    if "T" in text:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    return date.fromisoformat(text)


def _as_of_date(as_of) -> date:
    parsed = _parse_date(as_of)
    if parsed is None:
        raise ValueError("as_of date is required")
    return parsed


def load_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> dict:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_events(path: Path | str = DEFAULT_EVENTS_PATH) -> list[dict]:
    event_path = Path(path)
    if not event_path.exists():
        return []
    events = []
    with event_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                events.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {event_path}:{line_no}") from exc
    return events


def registry_hash(registry: dict) -> str:
    payload = json.dumps(registry, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def validate_record(record: dict) -> list[str]:
    issues = []
    ticker = record.get("ticker", "<missing>")
    missing = sorted(REQUIRED_RECORD_FIELDS - set(record))
    if missing:
        issues.append(f"{ticker}: missing fields {missing}")

    status = record.get("status")
    if status not in VALID_STATUSES:
        issues.append(f"{ticker}: invalid status {status!r}")

    if record.get("ticker") and record["ticker"] != record["ticker"].upper():
        issues.append(f"{ticker}: ticker must be uppercase")

    for field in (
        "discovered_as_of",
        "eligible_as_of",
        "first_trade_allowed_as_of",
        "status_effective_as_of",
        "decision_as_of",
        "data_available_as_of",
        "last_reviewed_at",
    ):
        if field in record:
            try:
                _parse_date(record[field])
            except (TypeError, ValueError) as exc:
                issues.append(f"{ticker}: invalid date field {field}: {exc}")

    for field in ("max_capital_scalar", "max_risk_scalar"):
        value = record.get(field)
        if value is not None and not isinstance(value, (int, float)):
            issues.append(f"{ticker}: {field} must be numeric")
        elif isinstance(value, (int, float)) and value < 0:
            issues.append(f"{ticker}: {field} must be non-negative")

    if record.get("status") in TRADEABLE_STATUSES and not record.get(
        "first_trade_allowed_as_of"
    ):
        issues.append(
            f"{ticker}: tradeable statuses require first_trade_allowed_as_of"
        )

    return issues


def validate_registry(registry: dict) -> list[str]:
    issues = []
    if registry.get("schema_version") != 1:
        issues.append("registry: schema_version must be 1")
    tickers = registry.get("tickers")
    if not isinstance(tickers, dict):
        return issues + ["registry: tickers must be an object"]
    for key, record in tickers.items():
        if key != key.upper():
            issues.append(f"{key}: registry key must be uppercase")
        if record.get("ticker") != key:
            issues.append(f"{key}: record ticker does not match registry key")
        issues.extend(validate_record(record))
    return issues


def replay_events_as_of(events: Iterable[dict], as_of) -> dict[str, dict]:
    cutoff = _as_of_date(as_of)
    state: dict[str, dict] = {}
    ordered = sorted(
        events,
        key=lambda e: (
            str(e.get("effective_as_of") or e.get("event_time") or ""),
            str(e.get("event_id") or ""),
        ),
    )
    for event in ordered:
        effective = _parse_date(event.get("effective_as_of") or event.get("event_time"))
        if effective is None or effective > cutoff:
            continue
        ticker = str(event.get("ticker") or "").upper()
        if not ticker:
            continue
        patch = deepcopy(event.get("record_patch") or {})
        patch.setdefault("ticker", ticker)
        if event.get("to_status"):
            patch["status"] = event["to_status"]
        current = state.get(ticker, {})
        current.update(patch)
        state[ticker] = current
    return state


def records_as_of(
    as_of,
    *,
    registry_path: Path | str = DEFAULT_REGISTRY_PATH,
    events_path: Path | str = DEFAULT_EVENTS_PATH,
    prefer_events: bool = True,
) -> dict[str, dict]:
    events = load_events(events_path)
    if prefer_events and events:
        return replay_events_as_of(events, as_of)

    cutoff = _as_of_date(as_of)
    registry = load_registry(registry_path)
    out = {}
    for ticker, record in registry.get("tickers", {}).items():
        effective = _parse_date(record.get("status_effective_as_of"))
        if effective is not None and effective <= cutoff:
            out[ticker] = deepcopy(record)
    return out


def eligible_tickers_as_of(
    as_of,
    *,
    statuses: set[str] | None = None,
    require_trade_allowed: bool = True,
    registry_path: Path | str = DEFAULT_REGISTRY_PATH,
    events_path: Path | str = DEFAULT_EVENTS_PATH,
) -> list[str]:
    cutoff = _as_of_date(as_of)
    allowed_statuses = statuses or TRADEABLE_STATUSES
    records = records_as_of(
        cutoff,
        registry_path=registry_path,
        events_path=events_path,
    )
    tickers = []
    for ticker, record in records.items():
        if record.get("status") not in allowed_statuses:
            continue
        eligible = _parse_date(record.get("eligible_as_of"))
        if eligible is not None and eligible > cutoff:
            continue
        if require_trade_allowed:
            first_trade = _parse_date(record.get("first_trade_allowed_as_of"))
            if first_trade is None or first_trade > cutoff:
                continue
        tickers.append(ticker)
    return sorted(tickers)


def append_universe_event(event: dict, path: Path | str = DEFAULT_EVENTS_PATH) -> None:
    event_path = Path(path)
    event_path.parent.mkdir(parents=True, exist_ok=True)
    with event_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")
