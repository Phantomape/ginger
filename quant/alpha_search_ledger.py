"""Strict append-only storage for outcome-blind alpha-search decisions.

This ledger is deliberately narrower than an experiment or outcome ledger.  It
persists only the three discovery-time facts needed to reconstruct a search:

* ``candidate_snapshot`` -- the frozen hypothesis contract;
* ``preflight_decision`` -- the outcome-blind D0-D3 decision; and
* ``panel_selection`` -- the complete selection panel and its winner (if any).

Rows are immutable JSON objects.  Appends take an exclusive sidecar lock, read
and validate the complete existing population while holding that lock, and
replace ``existing_text + suffix`` through :func:`atomic_write_text`.  A bad
historical row therefore fails closed instead of being skipped.  Semantic
identity is distinct from physical ``event_id``: retrying the same identity and
payload is a no-op, while either an identity or an event-id collision with
different content is rejected.

No function in this module reads prices, outcomes, backtests, strategies, or
orders.  Realised-performance fields are rejected if a caller attempts to
smuggle them into a discovery event.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:  # Support package imports and direct ``quant/`` script execution.
    from .alpha_search_contract import (
        canonical_hash as _contract_canonical_hash,
        canonical_json as _contract_canonical_json,
    )
    from .data_paths import atomic_write_text, data_artifact_path
except ImportError:  # pragma: no cover - script-style import fallback.
    from alpha_search_contract import (  # type: ignore
        canonical_hash as _contract_canonical_hash,
        canonical_json as _contract_canonical_json,
    )
    from data_paths import atomic_write_text, data_artifact_path


SCHEMA_VERSION = 1
ALLOWED_RECORD_TYPES = frozenset(
    {"candidate_snapshot", "preflight_decision", "panel_selection"}
)
DEFAULT_LEDGER_PATH = data_artifact_path("alpha_search_decision_ledger")

_LOCK_TIMEOUT_SECONDS = 10.0
_LOCK_POLL_SECONDS = 0.02
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "record_type",
        "event_id",
        "identity",
        "identity_hash",
        "payload",
        "semantic_hash",
        "recorded_at",
        "record_hash",
    }
)
_IDENTITY_FIELDS = {
    "candidate_snapshot": ("selection_scope_id", "candidate_id"),
    "preflight_decision": (
        "selection_scope_id",
        "candidate_id",
        "preflight_version",
    ),
    "panel_selection": ("selection_scope_id",),
}
_RECORD_TYPE_ORDER = {
    "candidate_snapshot": 0,
    "preflight_decision": 1,
    "panel_selection": 2,
}

# Discovery storage must stay outcome blind.  These are exact normalised keys;
# legitimate contract fields such as ``outcome_blind`` and
# ``outcome_ledger`` are intentionally not caught by substring matching.
_FORBIDDEN_REALIZED_KEYS = frozenset(
    {
        "actual_ev_delta",
        "actual_pnl_delta",
        "actual_return",
        "after_metrics",
        "backtest",
        "backtest_result",
        "backtest_results",
        "before_metrics",
        "delta_metrics",
        "expected_value_score",
        "forward_return",
        "future_price",
        "future_return",
        "outcome",
        "outcome_label",
        "outcomes",
        "performance",
        "pnl",
        "profit",
        "realized_outcome",
        "realized_pnl",
        "realized_return",
        "realised_pnl",
        "realised_return",
        "return",
        "returns",
        "sharpe",
        "sharpe_daily",
        "strategy_total_return_pct",
        "total_pnl",
        "total_return_pct",
        "win_rate",
    }
)


class AlphaSearchLedgerError(ValueError):
    """Base class for fail-closed alpha-search ledger errors."""


class AlphaSearchLedgerValidationError(AlphaSearchLedgerError):
    """An event or an existing JSONL row violates the storage contract."""


class AlphaSearchLedgerConflictError(AlphaSearchLedgerError):
    """An existing identity or event id is paired with different content."""


class AlphaSearchLedgerLockError(AlphaSearchLedgerError):
    """The append lock could not be acquired within the bounded timeout."""


def _validate_json_value(value: Any, *, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AlphaSearchLedgerValidationError(f"{path} must be finite")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise AlphaSearchLedgerValidationError(
                    f"{path} keys must be strings"
                )
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise AlphaSearchLedgerValidationError(
        f"{path} contains non-JSON value {type(value).__name__}"
    )


def _canonical_json(value: Any) -> str:
    _validate_json_value(value, path="value")
    try:
        return _contract_canonical_json(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive.
        raise AlphaSearchLedgerValidationError(
            f"value is not canonical JSON: {exc}"
        ) from exc


def canonical_hash(value: Any) -> str:
    """Return a full SHA-256 digest over canonical JSON."""
    _validate_json_value(value, path="value")
    return _contract_canonical_hash(value)


def _normalise_mapping(value: Mapping[str, Any], *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AlphaSearchLedgerValidationError(f"{field} must be an object")
    # The JSON round trip freezes Mapping subclasses and catches unsupported
    # values while retaining deterministic list/dict semantics.
    raw = dict(value)
    _validate_json_value(raw, path=field)
    return json.loads(_canonical_json(raw))


def _normalise_recorded_at(value: Any) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        )
    if not isinstance(value, str) or not value.strip():
        raise AlphaSearchLedgerValidationError(
            "recorded_at must be a non-empty UTC ISO-8601 string"
        )
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AlphaSearchLedgerValidationError(
            "recorded_at must be a UTC ISO-8601 string"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise AlphaSearchLedgerValidationError("recorded_at must be UTC")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _find_forbidden_realized_field(value: Any, *, path: str = "payload") -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalised = str(key).strip().lower().replace("-", "_")
            current = f"{path}.{key}"
            forbidden_suffix = normalised.endswith(
                ("_realized_return", "_realized_pnl", "_forward_return")
            )
            if normalised in _FORBIDDEN_REALIZED_KEYS or forbidden_suffix:
                return current
            hit = _find_forbidden_realized_field(item, path=current)
            if hit is not None:
                return hit
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hit = _find_forbidden_realized_field(item, path=f"{path}[{index}]")
            if hit is not None:
                return hit
    return None


def _normalise_contract_payload(
    record_type: str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Dispatch a payload through its strict discovery contract validator.

    Imports are deliberately delayed: the contracts module owns schema
    evolution, while this module owns persistence.  Delaying the import avoids
    creating an import cycle and ensures a long-running CLI call sees the same
    validator implementation used to build the current scope.
    """

    try:
        try:
            from .alpha_search_contract import (
                normalize_preflight_decision,
                normalize_selection_panel,
                validate_candidate_semantic_id,
            )
        except ImportError:  # pragma: no cover - direct quant/ execution.
            from alpha_search_contract import (  # type: ignore
                normalize_preflight_decision,
                normalize_selection_panel,
                validate_candidate_semantic_id,
            )
        validators = {
            # Active durable storage does not accept legacy/human aliases.  A
            # migration must explicitly rebuild the canonical cand- content ID
            # before calling this ledger.
            "candidate_snapshot": lambda value: validate_candidate_semantic_id(
                value
            ).to_dict(),
            "preflight_decision": normalize_preflight_decision,
            "panel_selection": normalize_selection_panel,
        }
        validator = validators[record_type]
        normalised = validator(payload)
    except KeyError as exc:  # pragma: no cover - guarded by the allow-list.
        raise AlphaSearchLedgerValidationError(
            f"unsupported record_type {record_type!r}"
        ) from exc
    except Exception as exc:
        raise AlphaSearchLedgerValidationError(
            f"{record_type} payload failed strict contract validation: {exc}"
        ) from exc
    return _normalise_mapping(normalised, field=f"{record_type}.payload")


def _natural_identity(
    record_type: str,
    payload: Mapping[str, Any],
    *,
    selection_scope_id: str | None = None,
) -> dict[str, Any]:
    fields = _IDENTITY_FIELDS[record_type]
    identity: dict[str, Any] = {}
    for field in fields:
        if field == "selection_scope_id" and record_type == "candidate_snapshot":
            value = selection_scope_id
        elif field not in payload:
            raise AlphaSearchLedgerValidationError(
                f"{record_type} payload is missing natural identity field {field!r}"
            )
        else:
            value = payload[field]
        if field in {"candidate_id", "selection_scope_id"}:
            if not isinstance(value, str) or not value.strip():
                raise AlphaSearchLedgerValidationError(
                    f"{record_type}.{field} must be a non-empty string"
                )
            value = value.strip()
        elif field == "preflight_version":
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                raise AlphaSearchLedgerValidationError(
                    "preflight_decision.preflight_version must be a string or integer"
                )
            if isinstance(value, str) and not value.strip():
                raise AlphaSearchLedgerValidationError(
                    "preflight_decision.preflight_version must not be empty"
                )
            value = value.strip() if isinstance(value, str) else value
        identity[field] = value
    return identity


def _semantic_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": row["schema_version"],
        "record_type": row["record_type"],
        "identity": row["identity"],
        "payload": row["payload"],
    }


def _record_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "record_hash"}


def make_alpha_search_event(
    *,
    record_type: str,
    payload: Mapping[str, Any],
    identity: Mapping[str, Any] | None = None,
    selection_scope_id: str | None = None,
    event_id: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Build and hash one immutable discovery event.

    Identity is derived from the record type's stable natural key.  A caller
    may provide ``identity`` as an assertion, but it must equal that derived
    key exactly; content hashes and timestamps are never identity fields.
    ``recorded_at`` is excluded from semantic identity, so retrying later is
    idempotent.
    """

    if record_type not in ALLOWED_RECORD_TYPES:
        raise AlphaSearchLedgerValidationError(
            f"record_type must be one of {sorted(ALLOWED_RECORD_TYPES)}"
        )
    normalised_payload = _normalise_mapping(payload, field="payload")
    forbidden = _find_forbidden_realized_field(normalised_payload)
    if forbidden is not None:
        raise AlphaSearchLedgerValidationError(
            f"realized outcome/backtest field is forbidden in discovery ledger: {forbidden}"
        )
    normalised_payload = _normalise_contract_payload(record_type, normalised_payload)
    asserted_identity = (
        None if identity is None else _normalise_mapping(identity, field="identity")
    )
    scope_hint = selection_scope_id
    if record_type == "candidate_snapshot" and scope_hint is None and asserted_identity:
        candidate_scope = asserted_identity.get("selection_scope_id")
        scope_hint = candidate_scope if isinstance(candidate_scope, str) else None
    expected_identity = _natural_identity(
        record_type,
        normalised_payload,
        selection_scope_id=scope_hint,
    )
    if selection_scope_id is not None and (
        expected_identity.get("selection_scope_id") != selection_scope_id.strip()
        if isinstance(selection_scope_id, str)
        else True
    ):
        raise AlphaSearchLedgerValidationError(
            "selection_scope_id assertion does not match payload natural key"
        )
    if asserted_identity is None:
        normalised_identity = expected_identity
    else:
        normalised_identity = asserted_identity
        if normalised_identity != expected_identity:
            raise AlphaSearchLedgerValidationError(
                f"{record_type} identity must equal its stable natural key: "
                f"expected={expected_identity!r} actual={normalised_identity!r}"
            )

    identity_hash = canonical_hash(
        {"record_type": record_type, "identity": normalised_identity}
    )
    resolved_event_id = event_id or f"ase:{identity_hash[:32]}"
    if not isinstance(resolved_event_id, str) or not _EVENT_ID_PATTERN.fullmatch(
        resolved_event_id
    ):
        raise AlphaSearchLedgerValidationError(
            "event_id must be 1-128 safe identifier characters"
        )

    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": record_type,
        "event_id": resolved_event_id,
        "identity": normalised_identity,
        "identity_hash": identity_hash,
        "payload": normalised_payload,
        "semantic_hash": "",
        "recorded_at": _normalise_recorded_at(recorded_at),
        "record_hash": "",
    }
    row["semantic_hash"] = canonical_hash(_semantic_payload(row))
    row["record_hash"] = canonical_hash(_record_payload(row))
    return row


def validate_alpha_search_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Strictly validate one stored event and return a detached dictionary."""

    if not isinstance(event, Mapping):
        raise AlphaSearchLedgerValidationError("event must be a JSON object")
    row = dict(event)
    fields = frozenset(row)
    if fields != _REQUIRED_FIELDS:
        missing = sorted(_REQUIRED_FIELDS - fields)
        unknown = sorted(fields - _REQUIRED_FIELDS)
        raise AlphaSearchLedgerValidationError(
            f"event fields mismatch: missing={missing} unknown={unknown}"
        )
    if row["schema_version"] != SCHEMA_VERSION:
        raise AlphaSearchLedgerValidationError(
            f"unsupported schema_version {row['schema_version']!r}"
        )
    if row["record_type"] not in ALLOWED_RECORD_TYPES:
        raise AlphaSearchLedgerValidationError(
            f"unsupported record_type {row['record_type']!r}"
        )
    if not isinstance(row["event_id"], str) or not _EVENT_ID_PATTERN.fullmatch(
        row["event_id"]
    ):
        raise AlphaSearchLedgerValidationError("invalid event_id")
    row["identity"] = _normalise_mapping(row["identity"], field="identity")
    if not row["identity"]:
        raise AlphaSearchLedgerValidationError("identity must not be empty")
    row["payload"] = _normalise_mapping(row["payload"], field="payload")
    forbidden = _find_forbidden_realized_field(row["payload"])
    if forbidden is not None:
        raise AlphaSearchLedgerValidationError(
            f"realized outcome/backtest field is forbidden in discovery ledger: {forbidden}"
        )
    canonical_payload = _normalise_contract_payload(row["record_type"], row["payload"])
    if canonical_hash(canonical_payload) != canonical_hash(row["payload"]):
        raise AlphaSearchLedgerValidationError(
            f"{row['record_type']} payload is not in canonical contract form"
        )
    stored_scope = row["identity"].get("selection_scope_id")
    expected_identity = _natural_identity(
        row["record_type"],
        canonical_payload,
        selection_scope_id=stored_scope if isinstance(stored_scope, str) else None,
    )
    if row["identity"] != expected_identity:
        raise AlphaSearchLedgerValidationError(
            f"{row['record_type']} identity does not match payload natural key"
        )
    row["payload"] = canonical_payload
    row["recorded_at"] = _normalise_recorded_at(row["recorded_at"])

    for field in ("identity_hash", "semantic_hash", "record_hash"):
        if not isinstance(row[field], str) or not _HASH_PATTERN.fullmatch(row[field]):
            raise AlphaSearchLedgerValidationError(
                f"{field} must be a lowercase SHA-256 digest"
            )
    expected_identity_hash = canonical_hash(
        {"record_type": row["record_type"], "identity": row["identity"]}
    )
    if row["identity_hash"] != expected_identity_hash:
        raise AlphaSearchLedgerValidationError("identity_hash mismatch")
    expected_semantic_hash = canonical_hash(_semantic_payload(row))
    if row["semantic_hash"] != expected_semantic_hash:
        raise AlphaSearchLedgerValidationError("semantic_hash mismatch")
    expected_record_hash = canonical_hash(_record_payload(row))
    if row["record_hash"] != expected_record_hash:
        raise AlphaSearchLedgerValidationError("record_hash mismatch")
    return row


def validate_alpha_search_events(
    events: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Validate a complete population, rejecting physical duplicates too."""

    validated: list[dict[str, Any]] = []
    by_event_id: dict[str, dict[str, Any]] = {}
    by_identity: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(events, start=1):
        try:
            row = validate_alpha_search_event(event)
        except AlphaSearchLedgerError as exc:
            raise AlphaSearchLedgerValidationError(f"event {index}: {exc}") from exc

        prior_id = by_event_id.get(row["event_id"])
        if prior_id is not None:
            if prior_id["semantic_hash"] != row["semantic_hash"]:
                raise AlphaSearchLedgerConflictError(
                    f"event_id {row['event_id']!r} has conflicting content"
                )
            raise AlphaSearchLedgerValidationError(
                f"duplicate physical event_id {row['event_id']!r}"
            )

        prior_identity = by_identity.get(row["identity_hash"])
        if prior_identity is not None:
            if prior_identity["semantic_hash"] != row["semantic_hash"]:
                raise AlphaSearchLedgerConflictError(
                    "semantic identity has conflicting content: "
                    f"{row['identity_hash']}"
                )
            raise AlphaSearchLedgerValidationError(
                f"duplicate physical identity {row['identity_hash']}"
            )

        by_event_id[row["event_id"]] = row
        by_identity[row["identity_hash"]] = row
        validated.append(row)
    return validated


def _candidate_rows_from_panel(panel: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw_candidates = panel.get("candidate_snapshots", panel.get("candidates"))
    if not isinstance(raw_candidates, list):
        raise AlphaSearchLedgerValidationError(
            "panel_selection payload must contain canonical candidate snapshots"
        )
    out: dict[str, Mapping[str, Any]] = {}
    for index, candidate in enumerate(raw_candidates):
        if not isinstance(candidate, Mapping):
            raise AlphaSearchLedgerValidationError(
                f"panel candidate {index} must be an object"
            )
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise AlphaSearchLedgerValidationError(
                f"panel candidate {index} has no candidate_id"
            )
        if candidate_id in out:
            raise AlphaSearchLedgerValidationError(
                f"panel contains duplicate candidate_id {candidate_id!r}"
            )
        out[candidate_id] = candidate
    return out


def validate_discovery_batch(
    events: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Validate event rows plus complete-scope relationships.

    When a ``panel_selection`` is present, the same batch must contain exactly
    the candidate and preflight event sets declared by that panel.  Embedded
    candidate/preflight payloads must match their standalone event payloads.
    This is checked before the ledger lock and before any write.
    """

    rows = validate_alpha_search_events(events)
    panels = [row for row in rows if row["record_type"] == "panel_selection"]
    if not panels:
        return rows
    if len(panels) != 1:
        raise AlphaSearchLedgerValidationError(
            "one discovery batch may contain exactly one panel_selection scope"
        )

    panel_event = panels[0]
    panel = panel_event["payload"]
    scope_id = panel["selection_scope_id"]
    panel_candidates = _candidate_rows_from_panel(panel)
    explicit_ids = panel.get("candidate_ids")
    if not isinstance(explicit_ids, list) or explicit_ids != sorted(panel_candidates):
        raise AlphaSearchLedgerValidationError(
            "panel candidate_ids must exactly match sorted candidate snapshots"
        )
    expected_ids = set(explicit_ids)

    candidate_events = {
        row["payload"]["candidate_id"]: row
        for row in rows
        if row["record_type"] == "candidate_snapshot"
    }
    if set(candidate_events) != expected_ids:
        raise AlphaSearchLedgerValidationError(
            "panel batch candidate_snapshot set is incomplete: "
            f"expected={sorted(expected_ids)!r} actual={sorted(candidate_events)!r}"
        )
    for candidate_id, embedded in panel_candidates.items():
        if candidate_events[candidate_id]["identity"].get("selection_scope_id") != scope_id:
            raise AlphaSearchLedgerValidationError(
                f"candidate snapshot scope mismatch for {candidate_id!r}"
            )
        if canonical_hash(candidate_events[candidate_id]["payload"]) != canonical_hash(
            embedded
        ):
            raise AlphaSearchLedgerValidationError(
                f"panel candidate snapshot differs from event payload for {candidate_id!r}"
            )

    preflight_rows = [
        row for row in rows if row["record_type"] == "preflight_decision"
    ]
    preflight_events = {
        row["payload"]["candidate_id"]: row
        for row in preflight_rows
    }
    if len(preflight_events) != len(preflight_rows):
        raise AlphaSearchLedgerValidationError(
            "panel batch must contain exactly one preflight version per candidate"
        )
    if set(preflight_events) != expected_ids:
        raise AlphaSearchLedgerValidationError(
            "panel batch preflight_decision set is incomplete: "
            f"expected={sorted(expected_ids)!r} actual={sorted(preflight_events)!r}"
        )
    for candidate_id, row in preflight_events.items():
        if row["payload"].get("selection_scope_id") != scope_id:
            raise AlphaSearchLedgerValidationError(
                f"preflight scope mismatch for candidate {candidate_id!r}"
            )

    embedded_preflights = panel.get("preflight_decisions")
    if embedded_preflights is not None:
        if not isinstance(embedded_preflights, Mapping):
            raise AlphaSearchLedgerValidationError(
                "panel preflight_decisions must be an object"
            )
        if set(embedded_preflights) != expected_ids:
            raise AlphaSearchLedgerValidationError(
                "panel embedded preflight_decisions set is incomplete"
            )
        for candidate_id, embedded in embedded_preflights.items():
            if canonical_hash(preflight_events[candidate_id]["payload"]) != canonical_hash(
                embedded
            ):
                raise AlphaSearchLedgerValidationError(
                    "panel preflight decision differs from event payload for "
                    f"{candidate_id!r}"
                )

    return sorted(
        rows,
        key=lambda row: (
            _RECORD_TYPE_ORDER[row["record_type"]],
            _canonical_json(row["identity"]),
        ),
    )


def _load_alpha_search_event_text(text: str, *, source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise AlphaSearchLedgerValidationError(
                f"blank JSONL row at {source}:{line_number}"
            )
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AlphaSearchLedgerValidationError(
                f"invalid JSON at {source}:{line_number}: {exc.msg}"
            ) from exc
        if not isinstance(row, dict):
            raise AlphaSearchLedgerValidationError(
                f"event at {source}:{line_number} must be a JSON object"
            )
        rows.append(row)
    return validate_alpha_search_events(rows)


def load_alpha_search_events(path: str | Path = DEFAULT_LEDGER_PATH) -> list[dict[str, Any]]:
    """Load and strictly validate the entire JSONL ledger."""

    ledger_path = Path(path)
    if not ledger_path.exists():
        return []
    try:
        text = ledger_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise AlphaSearchLedgerError(
            f"cannot read alpha-search ledger {ledger_path}: {exc}"
        ) from exc
    return _load_alpha_search_event_text(text, source=str(ledger_path))


@contextmanager
def _exclusive_ledger_lock(path: Path, *, timeout_seconds: float):
    """Small cross-process O_EXCL lock matching other immutable ledgers."""

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
        # Windows can report an already-open O_EXCL sidecar as either
        # FileExistsError or PermissionError depending on timing/AV state.
        except (FileExistsError, PermissionError) as exc:
            if time.monotonic() >= deadline:
                raise AlphaSearchLedgerLockError(
                    f"timed out waiting for alpha-search ledger lock {lock_path}"
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


def _coerce_batch_event(
    value: Mapping[str, Any],
    *,
    index: int,
    inherited_scope_id: str | None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AlphaSearchLedgerValidationError(f"batch event {index} must be an object")
    fields = frozenset(value)
    if fields == _REQUIRED_FIELDS:
        return validate_alpha_search_event(value)
    spec_fields = frozenset(
        {
            "record_type",
            "payload",
            "identity",
            "selection_scope_id",
            "event_id",
            "recorded_at",
        }
    )
    if not {"record_type", "payload"}.issubset(fields) or fields - spec_fields:
        raise AlphaSearchLedgerValidationError(
            f"batch event {index} is neither a stored event nor a valid event spec"
        )
    return make_alpha_search_event(
        record_type=value["record_type"],
        payload=value["payload"],
        identity=value.get("identity"),
        selection_scope_id=value.get("selection_scope_id", inherited_scope_id),
        event_id=value.get("event_id"),
        recorded_at=value.get("recorded_at"),
    )


def append_discovery_batch(
    path: str | Path,
    events: Iterable[Mapping[str, Any]],
    *,
    lock_timeout_seconds: float = _LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Append a complete discovery scope with one lock and atomic replace.

    ``events`` may contain fully built ledger rows or compact specs with
    ``record_type`` and ``payload``.  All rows are contract-validated and the
    complete panel relationship is checked before the lock is acquired.  A
    retry may contain rows already present; they are skipped only when semantic
    content is identical.  Any conflict aborts the whole batch.
    """

    if isinstance(events, (str, bytes, bytearray, Mapping)):
        raise AlphaSearchLedgerValidationError("events must be an iterable of objects")
    raw_events = list(events)
    panel_scope_hints = {
        str(payload.get("selection_scope_id"))
        for value in raw_events
        if isinstance(value, Mapping)
        and value.get("record_type") == "panel_selection"
        and isinstance((payload := value.get("payload")), Mapping)
        and isinstance(payload.get("selection_scope_id"), str)
        and payload.get("selection_scope_id")
    }
    if len(panel_scope_hints) > 1:
        raise AlphaSearchLedgerValidationError(
            "one discovery batch may not declare multiple panel scopes"
        )
    inherited_scope_id = next(iter(panel_scope_hints), None)
    proposed = [
        _coerce_batch_event(
            value,
            index=index,
            inherited_scope_id=inherited_scope_id,
        )
        for index, value in enumerate(raw_events)
    ]
    if not proposed:
        raise AlphaSearchLedgerValidationError("discovery batch must not be empty")
    rows = validate_discovery_batch(proposed)
    ledger_path = Path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        timeout = float(lock_timeout_seconds)
    except (TypeError, ValueError) as exc:
        raise AlphaSearchLedgerLockError(
            "lock_timeout_seconds must be a finite non-negative number"
        ) from exc
    if not math.isfinite(timeout) or timeout < 0:
        raise AlphaSearchLedgerLockError("lock_timeout_seconds must be non-negative")

    with _exclusive_ledger_lock(
        ledger_path, timeout_seconds=timeout
    ):
        try:
            existing_text = (
                ledger_path.read_text(encoding="utf-8-sig")
                if ledger_path.exists()
                else ""
            )
        except (OSError, UnicodeError) as exc:
            raise AlphaSearchLedgerError(
                f"cannot read alpha-search ledger {ledger_path}: {exc}"
            ) from exc
        existing = _load_alpha_search_event_text(
            existing_text, source=str(ledger_path)
        )

        by_event_id = {item["event_id"]: item for item in existing}
        by_identity = {item["identity_hash"]: item for item in existing}
        new_rows: list[dict[str, Any]] = []
        duplicate_rows: list[dict[str, Any]] = []
        event_results: list[dict[str, Any]] = []
        for row in rows:
            same_id = by_event_id.get(row["event_id"])
            same_identity = by_identity.get(row["identity_hash"])
            prior = same_id or same_identity
            if prior is not None:
                if (
                    prior["event_id"] == row["event_id"] or same_id is None
                ) and prior["identity_hash"] == row["identity_hash"] and prior[
                    "semantic_hash"
                ] == row["semantic_hash"]:
                    duplicate_rows.append(prior)
                    event_results.append(
                        {
                            "status": "duplicate",
                            "event_id": prior["event_id"],
                            "identity_hash": prior["identity_hash"],
                            "semantic_hash": prior["semantic_hash"],
                        }
                    )
                    continue
                collision = (
                    f"event_id {row['event_id']!r} / semantic identity "
                    f"{row['identity_hash']}"
                    if same_id is not None
                    else f"semantic identity {row['identity_hash']}"
                )
                raise AlphaSearchLedgerConflictError(
                    f"{collision} already has different content"
                )

            new_rows.append(row)
            by_event_id[row["event_id"]] = row
            by_identity[row["identity_hash"]] = row
            event_results.append(
                {
                    "status": "appended",
                    "event_id": row["event_id"],
                    "identity_hash": row["identity_hash"],
                    "semantic_hash": row["semantic_hash"],
                }
            )

        if new_rows:
            prefix = existing_text
            if prefix and not prefix.endswith("\n"):
                prefix += "\n"
            suffix = "".join(_canonical_json(row) + "\n" for row in new_rows)
            atomic_write_text(prefix + suffix, ledger_path)
        status = (
            "appended"
            if not duplicate_rows
            else "duplicate"
            if not new_rows
            else "partially_appended"
        )
        return {
            "status": status,
            "rows_written": len(new_rows),
            "rows_skipped_duplicate": len(duplicate_rows),
            "event_count": len(existing) + len(new_rows),
            "events": event_results,
            "path": str(ledger_path),
        }


def append_alpha_search_event(
    path: str | Path,
    event: Mapping[str, Any],
    *,
    lock_timeout_seconds: float = _LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Append one non-panel event through the batch transaction machinery."""

    batch = append_discovery_batch(
        path,
        [event],
        lock_timeout_seconds=lock_timeout_seconds,
    )
    item = batch["events"][0]
    return {
        **item,
        "rows_written": batch["rows_written"],
        "event_count": batch["event_count"],
        "path": batch["path"],
    }


def append_discovery_event(
    path: str | Path,
    *,
    record_type: str,
    payload: Mapping[str, Any],
    identity: Mapping[str, Any] | None = None,
    selection_scope_id: str | None = None,
    event_id: str | None = None,
    recorded_at: str | None = None,
    lock_timeout_seconds: float = _LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Build and append an event in one call."""

    event = make_alpha_search_event(
        record_type=record_type,
        payload=payload,
        identity=identity,
        selection_scope_id=selection_scope_id,
        event_id=event_id,
        recorded_at=recorded_at,
    )
    return append_alpha_search_event(
        path,
        event,
        lock_timeout_seconds=lock_timeout_seconds,
    )


# Compact aliases for callers that already operate inside the alpha-search
# namespace.  Keeping the explicit names above makes accidental use by an
# experiment/outcome ledger less likely.
load_events = load_alpha_search_events
append_event = append_alpha_search_event


__all__ = [
    "ALLOWED_RECORD_TYPES",
    "DEFAULT_LEDGER_PATH",
    "SCHEMA_VERSION",
    "AlphaSearchLedgerConflictError",
    "AlphaSearchLedgerError",
    "AlphaSearchLedgerLockError",
    "AlphaSearchLedgerValidationError",
    "append_alpha_search_event",
    "append_discovery_batch",
    "append_discovery_event",
    "append_event",
    "canonical_hash",
    "load_alpha_search_events",
    "load_events",
    "make_alpha_search_event",
    "validate_alpha_search_event",
    "validate_alpha_search_events",
    "validate_discovery_batch",
]
