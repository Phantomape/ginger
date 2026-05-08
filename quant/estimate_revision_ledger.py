"""Forward-only estimate revision ledger helpers.

The ledger is intentionally data-only. It does not rank candidates, size
positions, or alter the production signal path.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SNAPSHOT_RE = re.compile(r"earnings_snapshot_(\d{8})\.json$")
SCHEMA_VERSION = 1


def parse_snapshot_date(path: str | Path, payload: dict[str, Any] | None = None) -> date:
    """Return the as-of date encoded by an earnings snapshot."""
    payload = payload or {}
    raw = payload.get("date")
    if raw:
        return datetime.strptime(str(raw), "%Y%m%d").date()
    match = SNAPSHOT_RE.search(Path(path).name)
    if not match:
        raise ValueError(f"not an earnings snapshot path: {path}")
    return datetime.strptime(match.group(1), "%Y%m%d").date()


def load_snapshot_records(
    data_dir: str | Path,
    *,
    start: str | date | None = None,
    end: str | date | None = None,
) -> list[dict[str, Any]]:
    """Load earnings snapshot files with source file metadata."""
    root = Path(data_dir)
    start_date = _coerce_date(start) if start is not None else None
    end_date = _coerce_date(end) if end is not None else None
    records: list[dict[str, Any]] = []

    for path in sorted(root.glob("earnings_snapshot_*.json")):
        payload = _read_json(path)
        as_of_date = parse_snapshot_date(path, payload)
        if start_date and as_of_date < start_date:
            continue
        if end_date and as_of_date > end_date:
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        records.append(
            {
                "as_of_date": as_of_date,
                "path": path,
                "file_mtime_utc": mtime,
                "payload": payload,
            }
        )

    return sorted(records, key=lambda item: item["as_of_date"])


def build_revision_ledger_rows(
    snapshot_records: list[dict[str, Any]],
    *,
    as_of: str | date | None = None,
    generated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Build per-ticker estimate revision rows for one snapshot date.

    A row is usable for revision analysis only when the current and prior
    observation are both PIT-safe and refer to the same next earnings date.
    """
    if not snapshot_records:
        return []

    generated_at = generated_at or datetime.now(timezone.utc)
    target_date = _coerce_date(as_of) if as_of is not None else snapshot_records[-1]["as_of_date"]
    by_date = {record["as_of_date"]: record for record in snapshot_records}
    current = by_date.get(target_date)
    if current is None:
        raise ValueError(f"no earnings snapshot for {target_date.isoformat()}")

    history_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for record in snapshot_records:
        if record["as_of_date"] >= target_date:
            continue
        for ticker, item in (record["payload"].get("earnings") or {}).items():
            history_by_ticker.setdefault(ticker.upper(), []).append(
                _observation_from_snapshot(record, ticker, item)
            )

    rows: list[dict[str, Any]] = []
    current_pit_safe = _snapshot_pit_safe(current)
    for ticker, item in sorted((current["payload"].get("earnings") or {}).items()):
        ticker = ticker.upper()
        obs = _observation_from_snapshot(current, ticker, item)
        same_event_history = [
            prior
            for prior in history_by_ticker.get(ticker, [])
            if (
                obs["next_earnings_date"] is not None
                and prior["next_earnings_date"] == obs["next_earnings_date"]
            )
        ]
        prior = same_event_history[-1] if same_event_history else None
        prior_7d = _latest_prior_at_least_days_back(same_event_history, target_date, 7)
        prior_30d = _latest_prior_at_least_days_back(same_event_history, target_date, 30)

        prior_eps = prior.get("eps_estimate") if prior else None
        delta_prev = _delta(obs["eps_estimate"], prior_eps)
        delta_7d = _delta(obs["eps_estimate"], prior_7d.get("eps_estimate") if prior_7d else None)
        delta_30d = _delta(obs["eps_estimate"], prior_30d.get("eps_estimate") if prior_30d else None)
        prior_pit_safe = bool(prior and prior.get("source_snapshot_pit_safe"))
        revision_pit_safe = bool(current_pit_safe and prior_pit_safe)
        usable = bool(
            revision_pit_safe
            and obs["next_earnings_date"] is not None
            and obs["eps_estimate"] is not None
            and prior_eps is not None
        )

        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at.isoformat(timespec="seconds"),
                "ticker": ticker,
                "as_of_date": target_date.isoformat(),
                "source_snapshot_path": _path_text(current["path"]),
                "source_snapshot_timestamp": current["payload"].get("timestamp"),
                "source_snapshot_mtime_utc": current["file_mtime_utc"].isoformat(timespec="seconds"),
                "source_snapshot_pit_safe": current_pit_safe,
                "next_earnings_date": obs["next_earnings_date"],
                "fiscal_period": item.get("fiscal_period"),
                "eps_estimate": obs["eps_estimate"],
                "revenue_estimate": item.get("revenue_estimate"),
                "vendor_asof": item.get("vendor_asof"),
                "source_retrieved_at": current["payload"].get("timestamp"),
                "prior_snapshot_date": prior["as_of_date"] if prior else None,
                "prior_snapshot_eps_estimate": prior_eps,
                "prior_snapshot_pit_safe": prior_pit_safe,
                "eps_estimate_delta_prev": delta_prev,
                "eps_estimate_delta_7d": delta_7d,
                "eps_estimate_delta_30d": delta_30d,
                "revision_direction_prev": _direction(delta_prev),
                "same_event_history_count": len(same_event_history),
                "same_event_revision_identifiable": obs["next_earnings_date"] is not None,
                "pit_safe_flag": usable,
                "estimate_revision_usable": usable,
                "pit_caveat": _pit_caveat(current_pit_safe, prior, obs),
            }
        )

    return rows


def summarize_ledger_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return compact coverage and usability metrics for a ledger run."""
    rows_with_eps = [row for row in rows if row.get("eps_estimate") is not None]
    usable = [row for row in rows if row.get("estimate_revision_usable")]
    up = [row for row in usable if row.get("revision_direction_prev") == "up"]
    down = [row for row in usable if row.get("revision_direction_prev") == "down"]
    return {
        "schema_version": SCHEMA_VERSION,
        "row_count": len(rows),
        "tickers_with_eps_estimate": len(rows_with_eps),
        "rows_with_next_earnings_date": sum(row.get("next_earnings_date") is not None for row in rows),
        "rows_with_prior_same_event": sum(row.get("prior_snapshot_eps_estimate") is not None for row in rows),
        "estimate_revision_usable_rows": len(usable),
        "up_revision_rows": len(up),
        "down_revision_rows": len(down),
        "pit_safe_rate": round(len(usable) / len(rows), 6) if rows else None,
    }


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _observation_from_snapshot(
    record: dict[str, Any],
    ticker: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ticker": ticker.upper(),
        "as_of_date": record["as_of_date"].isoformat(),
        "next_earnings_date": item.get("next_earnings_date"),
        "eps_estimate": _float_or_none(item.get("eps_estimate")),
        "source_snapshot_pit_safe": _snapshot_pit_safe(record),
    }


def _snapshot_pit_safe(record: dict[str, Any]) -> bool:
    # EOD snapshots may be written after the U.S. close and land on the next
    # UTC date. Anything later than that is treated as reconstructed/backfilled.
    return record["file_mtime_utc"].date() <= (record["as_of_date"] + timedelta(days=1))


def _latest_prior_at_least_days_back(
    same_event_history: list[dict[str, Any]],
    target_date: date,
    days: int,
) -> dict[str, Any] | None:
    cutoff = target_date.toordinal() - days
    candidates = [
        item
        for item in same_event_history
        if _coerce_date(item["as_of_date"]).toordinal() <= cutoff
    ]
    return candidates[-1] if candidates else None


def _pit_caveat(
    current_pit_safe: bool,
    prior: dict[str, Any] | None,
    obs: dict[str, Any],
) -> str | None:
    if obs["next_earnings_date"] is None:
        return "missing_next_earnings_date"
    if prior is None:
        return "no_prior_same_event_snapshot"
    if not current_pit_safe:
        return "current_snapshot_created_after_asof"
    if not prior.get("source_snapshot_pit_safe"):
        return "prior_snapshot_created_after_asof"
    return None


def _delta(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None:
        return None
    return round(current - prior, 6)


def _direction(delta: float | None) -> str | None:
    if delta is None:
        return None
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "flat"


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _path_text(path: str | Path) -> str:
    return str(path).replace("\\", "/")
