"""Read-only adapter for point-in-time universe governance.

Phase 1 adapter: expose universe registry state without changing the trading
universe used by run.py/backtester.py. Callers must opt in and pass the result
to reports only until a later production-parity phase enables consumption.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from universe_manager import (
    DEFAULT_EVENTS_PATH,
    DEFAULT_REGISTRY_PATH,
    TRADEABLE_STATUSES,
    load_events,
    load_registry,
    records_as_of,
    registry_hash,
)


SEGMENT_STATUSES = (
    "core",
    "pilot",
    "limited_production",
    "research",
    "specialist",
    "quarantine",
    "retired",
)


def file_hash(path: Path | str) -> str | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _default_core_universe() -> list[str]:
    # Imported lazily so tests can pass an explicit universe without touching
    # yfinance/bootstrap-heavy modules.
    from data_layer import get_universe

    return get_universe()


def universe_segments_as_of(
    as_of,
    *,
    core_universe: list[str] | None = None,
    registry_path: Path | str = DEFAULT_REGISTRY_PATH,
    events_path: Path | str = DEFAULT_EVENTS_PATH,
) -> dict:
    """Return read-only universe segments for a point-in-time date.

    `core_universe` represents the current production watchlist path. Registered
    non-core names are visible in their own segments but are not added to
    `core_trade_universe`.
    """
    registry = load_registry(registry_path)
    events = load_events(events_path)
    records = records_as_of(
        as_of,
        registry_path=registry_path,
        events_path=events_path,
        prefer_events=True,
    )

    segments = {status: [] for status in SEGMENT_STATUSES}
    for ticker, record in records.items():
        status = record.get("status")
        if status in segments:
            segments[status].append(ticker)

    for tickers in segments.values():
        tickers.sort()

    base_core = sorted({t.upper() for t in (core_universe or _default_core_universe())})
    registry_core = set(segments["core"])
    governance_non_core = {
        ticker
        for status, tickers in segments.items()
        if status != "core"
        for ticker in tickers
    }

    # Core trade list remains the legacy production universe plus explicit
    # registry-core records only. Pilot/research/specialist names do not leak in.
    core_trade_universe = sorted((set(base_core) | registry_core) - governance_non_core)
    observation_universe = sorted(
        set(segments["pilot"])
        | set(segments["limited_production"])
        | set(segments["research"])
        | set(segments["specialist"])
    )

    tradeable_governance = sorted(
        ticker
        for ticker, record in records.items()
        if record.get("status") in TRADEABLE_STATUSES
    )

    return {
        "as_of": str(as_of),
        "mode": "read_only",
        "protocol_version": registry.get("protocol_version"),
        "schema_version": registry.get("schema_version"),
        "registry_hash": registry_hash(registry),
        "event_ledger_hash": file_hash(events_path),
        "event_count": len(events),
        "segments": segments,
        "core_trade_universe": core_trade_universe,
        "observation_universe": observation_universe,
        "governance_tradeable_universe": tradeable_governance,
        "records": records,
        "production_impact": {
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
    }


def save_universe_state_report(state: dict, path: Path | str) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
