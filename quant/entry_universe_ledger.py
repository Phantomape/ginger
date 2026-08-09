"""Immutable point-in-time entry-universe membership snapshots.

Each JSONL row is a *full-membership replacement* effective on one calendar
date.  It is not a delta.  That makes the as-of contract deliberately simple:
before the first snapshot membership is unknown (and therefore resolves to an
empty entry set); on or after a snapshot, the latest snapshot at or before the
requested date is authoritative.

The ledger separates three hashes:

``membership_hash``
    Canonical hash of the sorted ticker set only.
``snapshot_hash``
    Canonical semantic identity of the dated snapshot.  ``generated_at`` is
    excluded so a same-input rerun remains idempotent.
``record_hash``
    Integrity hash of the exact persisted JSON object, including
    ``generated_at`` and ``snapshot_hash``.

Appending uses a small exclusive lock plus an atomic same-directory replace.
An identical same-day semantic snapshot is a no-op.  Any other same-day row is
rejected rather than silently choosing one membership history.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import os
import time
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

try:  # Support both ``import quant.entry_universe_ledger`` and quant/ scripts.
    from .data_paths import atomic_write_text
except ImportError:  # pragma: no cover - exercised by script-style imports.
    from data_paths import atomic_write_text


SCHEMA_VERSION = 1
RECORD_TYPE = "entry_universe_membership_snapshot"
SNAPSHOT_SEMANTICS = "full_membership_replace"
BEFORE_FIRST_SNAPSHOT_POLICY = "unknown_empty"

_HASH_HEX_LENGTH = 64
_LOCK_TIMEOUT_SECONDS = 10.0
_LOCK_POLL_SECONDS = 0.02
_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "record_type",
        "snapshot_semantics",
        "effective_as_of",
        "generated_at",
        "tickers",
        "ticker_count",
        "membership_hash",
        "source",
        "source_hash",
        "clean_cutoff",
        "provenance",
        "snapshot_hash",
        "record_hash",
    }
)


class MembershipLedgerError(ValueError):
    """Base class for fail-closed membership-ledger errors."""


class MembershipSnapshotValidationError(MembershipLedgerError):
    """A snapshot does not satisfy the immutable schema or its hashes."""


class MembershipSnapshotConflictError(MembershipLedgerError):
    """Two semantically different full snapshots claim the same date."""


class MembershipLedgerLockError(MembershipLedgerError):
    """The append lock could not be acquired within the bounded timeout."""


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise MembershipSnapshotValidationError(
            f"value is not canonical JSON: {exc}"
        ) from exc


def canonical_hash(value: Any) -> str:
    """Return a full SHA-256 over deterministic canonical JSON."""

    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalise_date(value: Any, *, field: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    # pandas.Timestamp and similar date-like objects are accepted without
    # importing an optional dependency.
    if not isinstance(value, str) and hasattr(value, "date"):
        try:
            candidate = value.date()
        except Exception as exc:  # pragma: no cover - defensive custom object.
            raise MembershipSnapshotValidationError(
                f"{field} must be an ISO calendar date"
            ) from exc
        if isinstance(candidate, date):
            return candidate.isoformat()

    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except (TypeError, ValueError) as exc:
        raise MembershipSnapshotValidationError(
            f"{field} must be an ISO calendar date, got {value!r}"
        ) from exc
    if parsed.isoformat() != text:
        raise MembershipSnapshotValidationError(
            f"{field} must use canonical YYYY-MM-DD form, got {value!r}"
        )
    return text


def _normalise_generated_at(value: Any | None) -> str:
    if value is None:
        parsed = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise MembershipSnapshotValidationError(
                f"generated_at must be an ISO timestamp, got {value!r}"
            ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MembershipSnapshotValidationError(
            "generated_at must include an explicit timezone"
        )
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalise_tickers(tickers: Iterable[str]) -> list[str]:
    if isinstance(tickers, (str, bytes)):
        raise MembershipSnapshotValidationError(
            "tickers must be an iterable of symbols, not a single string"
        )

    normalised: set[str] = set()
    try:
        iterator = iter(tickers)
    except TypeError as exc:
        raise MembershipSnapshotValidationError(
            "tickers must be an iterable of strings"
        ) from exc

    for raw in iterator:
        if not isinstance(raw, str):
            raise MembershipSnapshotValidationError(
                f"ticker values must be strings, got {raw!r}"
            )
        ticker = raw.strip().upper()
        if not ticker:
            raise MembershipSnapshotValidationError("ticker values cannot be blank")
        if len(ticker) > 64 or any(char.isspace() for char in ticker):
            raise MembershipSnapshotValidationError(
                f"ticker must be a compact symbol, got {raw!r}"
            )
        normalised.add(ticker)
    return sorted(normalised)


def membership_hash(tickers: Iterable[str]) -> str:
    """Return the canonical identity of a ticker membership set."""

    return canonical_hash({"tickers": _normalise_tickers(tickers)})


def _json_object_copy(value: Mapping[str, Any] | None, *, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise MembershipSnapshotValidationError(f"{field} must be a JSON object")
    for key in value:
        if not isinstance(key, str):
            raise MembershipSnapshotValidationError(
                f"{field} keys must be strings, got {key!r}"
            )
    # Round-trip through canonical JSON to reject non-JSON and non-finite
    # values and to detach the immutable ledger row from caller-owned objects.
    return json.loads(_canonical_json(dict(value)))


def _optional_text(value: Any | None, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise MembershipSnapshotValidationError(
            f"{field} must be null or a non-empty string"
        )
    return value.strip()


def _snapshot_semantic_payload(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in snapshot.items()
        if key not in {"generated_at", "snapshot_hash", "record_hash"}
    }


def _snapshot_record_payload(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in snapshot.items()
        if key != "record_hash"
    }


def build_membership_snapshot(
    *,
    effective_as_of: Any,
    tickers: Iterable[str],
    source: str,
    source_hash: str | None = None,
    clean_cutoff: Any | None = None,
    provenance: Mapping[str, Any] | None = None,
    generated_at: Any | None = None,
) -> dict[str, Any]:
    """Build one deterministic full-membership snapshot.

    ``generated_at`` is operational provenance and is deliberately excluded
    from ``snapshot_hash``.  Put only stable facts in ``provenance``; changing
    those facts on the same effective date correctly creates a conflict.
    """

    if not isinstance(source, str) or not source.strip():
        raise MembershipSnapshotValidationError("source must be a non-empty string")

    normalised_tickers = _normalise_tickers(tickers)
    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        "snapshot_semantics": SNAPSHOT_SEMANTICS,
        "effective_as_of": _normalise_date(
            effective_as_of, field="effective_as_of"
        ),
        "generated_at": _normalise_generated_at(generated_at),
        "tickers": normalised_tickers,
        "ticker_count": len(normalised_tickers),
        "membership_hash": membership_hash(normalised_tickers),
        "source": source.strip(),
        "source_hash": _optional_text(source_hash, field="source_hash"),
        "clean_cutoff": (
            _normalise_date(clean_cutoff, field="clean_cutoff")
            if clean_cutoff is not None
            else None
        ),
        "provenance": _json_object_copy(provenance, field="provenance"),
    }
    snapshot["snapshot_hash"] = canonical_hash(
        _snapshot_semantic_payload(snapshot)
    )
    snapshot["record_hash"] = canonical_hash(_snapshot_record_payload(snapshot))
    return snapshot


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _HASH_HEX_LENGTH
        and value == value.lower()
        and all(char in "0123456789abcdef" for char in value)
    )


def validate_membership_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Validate hashes and the strict v1 schema, returning a detached copy."""

    if not isinstance(snapshot, Mapping):
        raise MembershipSnapshotValidationError("snapshot must be a JSON object")

    fields = set(snapshot)
    missing = sorted(_REQUIRED_FIELDS - fields)
    extra = sorted(fields - _REQUIRED_FIELDS)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing fields {missing}")
        if extra:
            details.append(f"unknown fields {extra}")
        raise MembershipSnapshotValidationError("; ".join(details))

    row = _json_object_copy(snapshot, field="snapshot")
    if row["schema_version"] != SCHEMA_VERSION:
        raise MembershipSnapshotValidationError(
            f"schema_version must be {SCHEMA_VERSION}"
        )
    if row["record_type"] != RECORD_TYPE:
        raise MembershipSnapshotValidationError(
            f"record_type must be {RECORD_TYPE!r}"
        )
    if row["snapshot_semantics"] != SNAPSHOT_SEMANTICS:
        raise MembershipSnapshotValidationError(
            f"snapshot_semantics must be {SNAPSHOT_SEMANTICS!r}"
        )

    if _normalise_date(
        row["effective_as_of"], field="effective_as_of"
    ) != row["effective_as_of"]:
        raise MembershipSnapshotValidationError("effective_as_of is not canonical")
    if _normalise_generated_at(row["generated_at"]) != row["generated_at"]:
        raise MembershipSnapshotValidationError("generated_at is not canonical UTC")

    if not isinstance(row["tickers"], list):
        raise MembershipSnapshotValidationError("tickers must be a JSON array")
    normalised_tickers = _normalise_tickers(row["tickers"])
    if normalised_tickers != row["tickers"]:
        raise MembershipSnapshotValidationError(
            "tickers must be uppercase, sorted, and unique"
        )
    if type(row["ticker_count"]) is not int or row["ticker_count"] != len(
        normalised_tickers
    ):
        raise MembershipSnapshotValidationError(
            "ticker_count must exactly match tickers"
        )

    if not isinstance(row["source"], str) or row["source"] != row["source"].strip() or not row["source"]:
        raise MembershipSnapshotValidationError("source must be a trimmed non-empty string")
    _optional_text(row["source_hash"], field="source_hash")
    if row["clean_cutoff"] is not None and _normalise_date(
        row["clean_cutoff"], field="clean_cutoff"
    ) != row["clean_cutoff"]:
        raise MembershipSnapshotValidationError("clean_cutoff is not canonical")
    if not isinstance(row["provenance"], dict):
        raise MembershipSnapshotValidationError("provenance must be a JSON object")

    for field in ("membership_hash", "snapshot_hash", "record_hash"):
        if not _is_sha256(row[field]):
            raise MembershipSnapshotValidationError(
                f"{field} must be a lowercase SHA-256 hex digest"
            )

    expected_membership_hash = membership_hash(normalised_tickers)
    if row["membership_hash"] != expected_membership_hash:
        raise MembershipSnapshotValidationError("membership_hash mismatch")
    expected_snapshot_hash = canonical_hash(_snapshot_semantic_payload(row))
    if row["snapshot_hash"] != expected_snapshot_hash:
        raise MembershipSnapshotValidationError("snapshot_hash mismatch")
    expected_record_hash = canonical_hash(_snapshot_record_payload(row))
    if row["record_hash"] != expected_record_hash:
        raise MembershipSnapshotValidationError("record_hash mismatch")
    return row


def validate_membership_snapshots(
    snapshots: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Validate a ledger population and reject duplicate/conflicting dates."""

    validated: list[dict[str, Any]] = []
    by_date: dict[str, dict[str, Any]] = {}
    for index, snapshot in enumerate(snapshots, start=1):
        try:
            row = validate_membership_snapshot(snapshot)
        except MembershipLedgerError as exc:
            raise MembershipSnapshotValidationError(
                f"snapshot {index}: {exc}"
            ) from exc
        effective_as_of = row["effective_as_of"]
        prior = by_date.get(effective_as_of)
        if prior is not None:
            if prior["snapshot_hash"] == row["snapshot_hash"]:
                raise MembershipSnapshotValidationError(
                    f"duplicate physical snapshot for {effective_as_of}"
                )
            raise MembershipSnapshotConflictError(
                "conflicting membership snapshots for "
                f"{effective_as_of}: {prior['snapshot_hash']} != "
                f"{row['snapshot_hash']}"
            )
        by_date[effective_as_of] = row
        validated.append(row)

    return sorted(validated, key=lambda row: row["effective_as_of"])


def _load_membership_snapshot_text(text: str, *, source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MembershipSnapshotValidationError(
                f"invalid JSON at {source}:{line_number}: {exc.msg}"
            ) from exc
        if not isinstance(row, dict):
            raise MembershipSnapshotValidationError(
                f"snapshot at {source}:{line_number} must be a JSON object"
            )
        rows.append(row)
    return validate_membership_snapshots(rows)


def load_membership_snapshots(path: str | Path) -> list[dict[str, Any]]:
    """Load, strictly validate, and effective-date sort a JSONL ledger."""

    ledger_path = Path(path)
    if not ledger_path.exists():
        return []
    try:
        text = ledger_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MembershipLedgerError(f"cannot read membership ledger {ledger_path}: {exc}") from exc
    return _load_membership_snapshot_text(text, source=str(ledger_path))


def _ledger_hash(snapshots: Iterable[Mapping[str, Any]]) -> str:
    identities = [
        {
            "effective_as_of": row["effective_as_of"],
            "snapshot_hash": row["snapshot_hash"],
        }
        for row in sorted(snapshots, key=lambda item: item["effective_as_of"])
    ]
    return canonical_hash(identities)


def _ledger_record_hash(snapshots: Iterable[Mapping[str, Any]]) -> str:
    records = [
        {
            "effective_as_of": row["effective_as_of"],
            "record_hash": row["record_hash"],
        }
        for row in sorted(snapshots, key=lambda item: item["effective_as_of"])
    ]
    return canonical_hash(records)


@contextmanager
def _exclusive_ledger_lock(path: Path, *, timeout_seconds: float):
    lock_path = Path(f"{path}.lock")
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise MembershipLedgerLockError(
                    f"timed out waiting for membership ledger lock {lock_path}"
                ) from exc
            time.sleep(_LOCK_POLL_SECONDS)

    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
        os.fsync(descriptor)
        yield
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:  # pragma: no cover - external cleanup race.
            pass


def _append_result(
    *,
    status: str,
    persisted: Mapping[str, Any],
    snapshots: list[Mapping[str, Any]],
    path: Path,
) -> dict[str, Any]:
    return {
        "status": status,
        "path": str(path),
        "effective_as_of": persisted["effective_as_of"],
        "generated_at": persisted["generated_at"],
        "ticker_count": persisted["ticker_count"],
        "membership_hash": persisted["membership_hash"],
        "snapshot_hash": persisted["snapshot_hash"],
        "record_hash": persisted["record_hash"],
        "snapshot_count": len(snapshots),
        "ledger_hash": _ledger_hash(snapshots),
        "ledger_record_hash": _ledger_record_hash(snapshots),
    }


def append_membership_snapshot(
    path: str | Path,
    snapshot: Mapping[str, Any],
    *,
    lock_timeout_seconds: float = _LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Atomically append one immutable snapshot, idempotently by semantic hash.

    A different semantic snapshot for an already-present date raises
    :class:`MembershipSnapshotConflictError` and leaves the ledger untouched.
    """

    row = validate_membership_snapshot(snapshot)
    ledger_path = Path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_timeout_seconds < 0:
        raise MembershipLedgerLockError("lock_timeout_seconds must be non-negative")

    with _exclusive_ledger_lock(
        ledger_path, timeout_seconds=float(lock_timeout_seconds)
    ):
        try:
            existing_text = (
                ledger_path.read_text(encoding="utf-8")
                if ledger_path.exists()
                else ""
            )
        except OSError as exc:
            raise MembershipLedgerError(
                f"cannot read membership ledger {ledger_path}: {exc}"
            ) from exc
        existing = _load_membership_snapshot_text(
            existing_text, source=str(ledger_path)
        )

        same_day = next(
            (
                prior
                for prior in existing
                if prior["effective_as_of"] == row["effective_as_of"]
            ),
            None,
        )
        if same_day is not None:
            if same_day["snapshot_hash"] == row["snapshot_hash"]:
                return _append_result(
                    status="duplicate",
                    persisted=same_day,
                    snapshots=existing,
                    path=ledger_path,
                )
            raise MembershipSnapshotConflictError(
                "refusing conflicting full-membership snapshots for "
                f"{row['effective_as_of']}: existing="
                f"{same_day['snapshot_hash']} proposed={row['snapshot_hash']}"
            )

        prefix = existing_text
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        updated_text = prefix + _canonical_json(row) + "\n"
        atomic_write_text(updated_text, ledger_path)
        updated = sorted(existing + [row], key=lambda item: item["effective_as_of"])
        return _append_result(
            status="appended",
            persisted=row,
            snapshots=updated,
            path=ledger_path,
        )


class EntryUniverseResolver:
    """Callable latest-full-snapshot resolver for backtest entry eligibility."""

    def __init__(
        self,
        snapshots: Iterable[Mapping[str, Any]],
        *,
        ledger_path: str | Path | None = None,
    ) -> None:
        rows = validate_membership_snapshots(snapshots)
        self._snapshots = tuple(rows)
        self._effective_dates = tuple(
            date.fromisoformat(row["effective_as_of"]) for row in rows
        )
        self._ledger_path = str(Path(ledger_path)) if ledger_path is not None else None
        self._data_tickers = frozenset(
            ticker for row in rows for ticker in row["tickers"]
        )
        self._metadata = self._build_metadata()

    @classmethod
    def from_path(cls, path: str | Path) -> "EntryUniverseResolver":
        return cls(load_membership_snapshots(path), ledger_path=path)

    @property
    def data_tickers(self) -> frozenset[str]:
        """All tickers ever present, suitable for OHLCV preloading."""

        return self._data_tickers

    @property
    def metadata(self) -> dict[str, Any]:
        """Detached JSON-safe provenance and canonical ledger identities."""

        return deepcopy(self._metadata)

    def _build_metadata(self) -> dict[str, Any]:
        rows = list(self._snapshots)
        return {
            "schema_version": SCHEMA_VERSION,
            "record_type": RECORD_TYPE,
            "snapshot_semantics": SNAPSHOT_SEMANTICS,
            "before_first_snapshot_policy": BEFORE_FIRST_SNAPSHOT_POLICY,
            "ledger_path": self._ledger_path,
            "snapshot_count": len(rows),
            "first_effective_as_of": (
                rows[0]["effective_as_of"] if rows else None
            ),
            "last_effective_as_of": (
                rows[-1]["effective_as_of"] if rows else None
            ),
            "data_ticker_count": len(self._data_tickers),
            "data_tickers_hash": membership_hash(self._data_tickers),
            "ledger_hash": _ledger_hash(rows),
            "ledger_record_hash": _ledger_record_hash(rows),
            "snapshots": [
                {
                    "effective_as_of": row["effective_as_of"],
                    "generated_at": row["generated_at"],
                    "ticker_count": row["ticker_count"],
                    "membership_hash": row["membership_hash"],
                    "snapshot_hash": row["snapshot_hash"],
                    "record_hash": row["record_hash"],
                    "source": row["source"],
                    "source_hash": row["source_hash"],
                    "clean_cutoff": row["clean_cutoff"],
                    "provenance": deepcopy(row["provenance"]),
                }
                for row in rows
            ],
        }

    def resolve(self, as_of: Any) -> dict[str, Any]:
        """Return a provenance-rich as-of resolution.

        Before the first known snapshot, or for an empty ledger, ``tickers`` is
        empty and status explicitly says that membership is unknown.  An
        explicit empty full snapshot instead returns ``status='resolved'``.
        """

        as_of_text = _normalise_date(as_of, field="as_of")
        target = date.fromisoformat(as_of_text)
        index = bisect.bisect_right(self._effective_dates, target) - 1
        if index < 0:
            status = (
                "unknown_empty_ledger"
                if not self._snapshots
                else "unknown_before_first_snapshot"
            )
            return {
                "status": status,
                "as_of": as_of_text,
                "effective_as_of": None,
                "tickers": [],
                "ticker_count": 0,
                "membership_hash": None,
                "snapshot_hash": None,
                "record_hash": None,
                "source": None,
                "source_hash": None,
                "clean_cutoff": None,
                "provenance": {},
            }

        row = self._snapshots[index]
        return {
            "status": "resolved",
            "as_of": as_of_text,
            "effective_as_of": row["effective_as_of"],
            "tickers": list(row["tickers"]),
            "ticker_count": row["ticker_count"],
            "membership_hash": row["membership_hash"],
            "snapshot_hash": row["snapshot_hash"],
            "record_hash": row["record_hash"],
            "source": row["source"],
            "source_hash": row["source_hash"],
            "clean_cutoff": row["clean_cutoff"],
            "provenance": deepcopy(row["provenance"]),
        }

    def __call__(self, as_of: Any) -> set[str]:
        return set(self.resolve(as_of)["tickers"])


__all__ = [
    "BEFORE_FIRST_SNAPSHOT_POLICY",
    "EntryUniverseResolver",
    "MembershipLedgerError",
    "MembershipLedgerLockError",
    "MembershipSnapshotConflictError",
    "MembershipSnapshotValidationError",
    "RECORD_TYPE",
    "SCHEMA_VERSION",
    "SNAPSHOT_SEMANTICS",
    "append_membership_snapshot",
    "build_membership_snapshot",
    "canonical_hash",
    "load_membership_snapshots",
    "membership_hash",
    "validate_membership_snapshot",
    "validate_membership_snapshots",
]
