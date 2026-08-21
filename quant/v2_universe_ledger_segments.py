"""Opt-in checkpoint/segment sidecar storage for the V2 universe ledger.

The existing mixed JSONL ledger remains the logical truth and is not modified by
this module.  A constant-size ``HEAD.json`` selects one immutable checkpoint and
an optional hash-linked tail of one-transaction segments.  Compact rotation
retains the exact current event population, one tip manifest, and O(manifest
history) identity facts in the hot generation while preserving old immutable
generations for explicit exact replay.

The publisher, writer, state reader, and rotation remain opt-in and do not
change the legacy runtime reader, establish an external append anchor, or
upgrade any research/PIT/trading boundary.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .data_paths import _replace_with_retry
from .v2_contracts import (
    CalendarSession,
    EvidenceRecord,
    SessionClock,
    SourceContract,
    UniverseEvent,
    V2ContractValidationError,
    canonical_hash,
    canonical_json,
    validate_universe_event,
)
from .v2_universe_ledger import (
    _LOCK_TIMEOUT_SECONDS,
    V2UniverseLedgerError,
    _classify_v2_universe_batch_append,
    _exclusive_ledger_lock,
    _extend_clock_binding_registry,
    _instant,
    _load_ledger_text,
    _membership_semantic_rows,
    _prepare_v2_universe_batch_append,
    _validated_lock_timeout,
    _validate_manifest_event_bindings,
    _validate_manifest_clock_bindings,
    _validate_manifest_population_bindings,
    _validate_manifest_research_pit,
    _validate_manifest_input_registry,
    _validate_manifest_shape,
    validate_universe_event_population,
)


SCHEMA_VERSION = 1
HEAD_RECORD_TYPE = "v2_universe_segmented_head"
CHECKPOINT_RECORD_TYPE = "v2_universe_ledger_checkpoint"
COMPACT_CHECKPOINT_RECORD_TYPE = "v2_universe_ledger_compact_checkpoint"
SEGMENT_RECORD_TYPE = "v2_universe_ledger_segment"
STORAGE_CONTRACT = "v2_universe_checkpoint_segment_sidecar_v1"

_BOUNDARY = {
    "external_universe_coverage_status": "unverified",
    "pit_tier": "research_pit",
    "result_ceiling": "observed_only",
    "paper_live_eligible": False,
    "parity_status": "contract_only_unwired",
    "authority": "research_only",
    "trade_enabled": False,
    "external_append_anchor_status": "absent",
}

_HEAD_FIELDS = frozenset(
    {
        "schema_version",
        "record_type",
        "storage_contract",
        "checkpoint_hash",
        "tail_segment_hash",
        "event_count",
        "manifest_count",
        "head_manifest_id",
        "head_manifest_hash",
        "universe_id",
        "universe_definition_id",
        "universe_definition_version",
        "universe_definition_sha256",
        *_BOUNDARY,
        "head_hash",
    }
)

_CHECKPOINT_FIELDS = frozenset(
    {
        "schema_version",
        "record_type",
        "storage_contract",
        "events",
        "manifests",
        "identity_state",
        "event_count",
        "manifest_count",
        "head_manifest_id",
        "head_manifest_hash",
        "universe_id",
        "universe_definition_id",
        "universe_definition_version",
        "universe_definition_sha256",
        *_BOUNDARY,
        "checkpoint_hash",
    }
)

_COMPACT_CHECKPOINT_FIELDS = frozenset(
    {
        "schema_version",
        "record_type",
        "storage_contract",
        "events",
        "head_manifest",
        "identity_state",
        "compacted_from_head",
        "event_count",
        "manifest_count",
        "head_manifest_id",
        "head_manifest_hash",
        "universe_id",
        "universe_definition_id",
        "universe_definition_version",
        "universe_definition_sha256",
        *_BOUNDARY,
        "checkpoint_hash",
    }
)

_SEGMENT_FIELDS = frozenset(
    {
        "schema_version",
        "record_type",
        "storage_contract",
        "checkpoint_hash",
        "sequence",
        "previous_segment_hash",
        "events",
        "manifest",
        "before_event_count",
        "after_event_count",
        "before_manifest_count",
        "after_manifest_count",
        "previous_manifest_id",
        "previous_manifest_hash",
        "head_manifest_id",
        "head_manifest_hash",
        "universe_id",
        *_BOUNDARY,
        "segment_hash",
    }
)

_IDENTITY_STATE_FIELDS = frozenset(
    {
        "event_identities",
        "manifest_identities",
        "source_contract_registry",
        "evidence_record_registry",
        "clock_bindings",
        "rule_bindings",
        "mapping_bindings",
        "event_chain_heads",
        "memberships",
        "membership_snapshot_sha256",
        "pending_future_event_ids",
    }
)


class V2UniverseSegmentError(V2UniverseLedgerError):
    """A segmented sidecar record or reachable chain failed closed."""


def _fail(code: str, detail: str) -> None:
    raise V2UniverseSegmentError(code, detail)


def _hash_payload(row: Mapping[str, Any], hash_field: str) -> str:
    try:
        return canonical_hash(
            {
                key: deepcopy(value)
                for key, value in row.items()
                if key != hash_field
            }
        )
    except V2ContractValidationError as exc:
        raise V2UniverseSegmentError(exc.code, exc.detail) from exc


def _require_hash(value: Any, *, field: str, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        _fail("segmented_hash_required", f"{field} must be a lowercase SHA-256")
    return value


def _require_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail("segmented_text_required", f"{field} must be trimmed non-empty text")
    return value


def _require_count(value: Any, *, field: str, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        qualifier = "positive" if positive else "non-negative"
        _fail("segmented_count_invalid", f"{field} must be a {qualifier} integer")
    return value


def _validate_boundary(row: Mapping[str, Any]) -> None:
    for field, expected in _BOUNDARY.items():
        actual = row.get(field)
        if (
            type(expected) is bool
            and (type(actual) is not bool or actual is not expected)
        ) or (type(expected) is not bool and actual != expected):
            _fail(
                "segmented_boundary_escalation",
                f"{field} must remain {expected!r}",
            )


def _canonical_legacy_view(value: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, Mapping) or set(value) != {"events", "manifests"}:
        _fail(
            "segmented_legacy_view_invalid",
            "legacy view must contain exactly events and manifests",
        )
    events = value["events"]
    manifests = value["manifests"]
    if not isinstance(events, list) or not isinstance(manifests, list):
        _fail("segmented_legacy_view_invalid", "events and manifests must be arrays")
    event_ids: list[str] = []
    for event in events:
        if not isinstance(event, Mapping):
            _fail("segmented_legacy_view_invalid", "event rows must be objects")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            _fail("segmented_legacy_view_invalid", "event rows need stable event_id values")
        event_ids.append(event_id)
    if len(event_ids) != len(set(event_ids)):
        _fail(
            "segmented_event_population_mismatch",
            "every supplied physical event_id must appear exactly once",
        )

    manifest_by_batch: dict[str, Mapping[str, Any]] = {}
    for item in manifests:
        if not isinstance(item, Mapping):
            _fail("segmented_legacy_view_invalid", "manifest rows must be objects")
        batch_id = item.get("event_batch_id")
        if not isinstance(batch_id, str) or not batch_id:
            _fail("segmented_legacy_view_invalid", "manifests need event_batch_id values")
        if batch_id in manifest_by_batch:
            _fail("segmented_legacy_view_invalid", "event_batch_id values must be unique")
        manifest_by_batch[batch_id] = item
    rows: list[Mapping[str, Any]] = []
    committed_ids: set[str] = set()
    for manifest in manifests:
        raw_batch_ids = manifest.get("batch_event_ids")
        if not isinstance(raw_batch_ids, list) or any(
            not isinstance(item, str) or not item for item in raw_batch_ids
        ):
            _fail("segmented_legacy_view_invalid", "batch_event_ids must be text arrays")
        batch_ids = set(raw_batch_ids)
        if len(batch_ids) != len(raw_batch_ids) or batch_ids & committed_ids:
            _fail(
                "segmented_event_population_mismatch",
                "manifest batches must partition physical event rows exactly once",
            )
        for event in events:
            event_id = event.get("event_id")
            if event_id in batch_ids:
                rows.append(event)
                committed_ids.add(event_id)
        rows.append(manifest)
    if committed_ids != set(event_ids):
        _fail(
            "segmented_event_population_mismatch",
            "every supplied event row must belong to exactly one committed batch",
        )
    try:
        text = "".join(canonical_json(row) + "\n" for row in rows)
        return _load_ledger_text(text, source="segmented contract input", allow_empty=False)
    except (V2UniverseLedgerError, V2ContractValidationError) as exc:
        raise V2UniverseSegmentError(exc.code, exc.detail) from exc


def _identity_state(loaded: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    events = [validate_universe_event(item) for item in loaded["events"]]
    manifests = list(loaded["manifests"])
    head = manifests[-1]
    clock_bindings: dict[str, dict[str, str]] = {}
    for manifest in manifests:
        for prefix in ("session_clock", "effective_session_clock"):
            clock_id = manifest[f"{prefix}_id"]
            clock_bindings[clock_id] = {
                "semantic_hash": manifest[f"{prefix}_hash"],
                "record_hash": manifest[f"{prefix}_record_hash"],
                "calendar_evidence_id": manifest[
                    f"{prefix}_calendar_evidence_id"
                ],
                "calendar_evidence_record_hash": manifest[
                    f"{prefix}_calendar_evidence_record_hash"
                ],
            }
    rules = {
        (event.rule_id, event.rule_version): event.rule_sha256 for event in events
    }
    mappings = {
        event.security_mapping.mapping_id: event.security_mapping.mapping_sha256
        for event in events
    }
    _, chain_heads = validate_universe_event_population(
        events, universe_id=head["universe_id"]
    )
    membership_as_of = _instant(
        head["membership_as_of"], field="checkpoint.membership_as_of"
    )[1]
    pending_ids = sorted(
        event.event_id
        for event in events
        if _instant(event.effective_at, field="checkpoint.event.effective_at")[1]
        > membership_as_of
    )
    return {
        "event_identities": [
            {
                "event_id": event.event_id,
                "semantic_hash": event.semantic_hash,
                "event_hash": event.event_hash,
            }
            for event in sorted(events, key=lambda item: item.event_id)
        ],
        "manifest_identities": [
            {
                "manifest_id": item["manifest_id"],
                "manifest_hash": item["manifest_hash"],
                "event_batch_id": item["event_batch_id"],
            }
            for item in manifests
        ],
        "source_contract_registry": deepcopy(head["source_contract_registry"]),
        "evidence_record_registry": deepcopy(head["evidence_record_registry"]),
        "clock_bindings": dict(sorted(clock_bindings.items())),
        "rule_bindings": [
            {"rule_id": key[0], "rule_version": key[1], "rule_sha256": value}
            for key, value in sorted(rules.items())
        ],
        "mapping_bindings": [
            {"mapping_id": key, "mapping_sha256": value}
            for key, value in sorted(mappings.items())
        ],
        "event_chain_heads": chain_heads,
        "memberships": deepcopy(head["memberships"]),
        "membership_snapshot_sha256": head["membership_snapshot_sha256"],
        "pending_future_event_ids": pending_ids,
    }


def _compact_identity_state(
    loaded: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Add the bounded manifest facts needed for archive-free retry checks."""

    state = _identity_state(loaded)
    previous_sources: set[str] = set()
    previous_evidence: set[str] = set()
    for identity, manifest in zip(
        state["manifest_identities"], loaded["manifests"], strict=True
    ):
        source_ids = set(manifest["source_contract_registry"])
        evidence_ids = set(manifest["evidence_record_registry"])
        identity["semantic_hash"] = manifest["semantic_hash"]
        identity["introduced_source_contract_ids"] = sorted(
            source_ids - previous_sources
        )
        identity["introduced_evidence_record_ids"] = sorted(
            evidence_ids - previous_evidence
        )
        previous_sources = source_ids
        previous_evidence = evidence_ids
    return state


def _base_record(record_type: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": record_type,
        "storage_contract": STORAGE_CONTRACT,
        **_BOUNDARY,
    }


def _build_checkpoint(loaded: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    events = [deepcopy(dict(item)) for item in loaded["events"]]
    manifests = [deepcopy(dict(item)) for item in loaded["manifests"]]
    head = manifests[-1]
    row = {
        **_base_record(CHECKPOINT_RECORD_TYPE),
        "events": events,
        "manifests": manifests,
        "identity_state": _identity_state({"events": events, "manifests": manifests}),
        "event_count": len(events),
        "manifest_count": len(manifests),
        "head_manifest_id": head["manifest_id"],
        "head_manifest_hash": head["manifest_hash"],
        "universe_id": head["universe_id"],
        "universe_definition_id": head["universe_definition_id"],
        "universe_definition_version": head["universe_definition_version"],
        "universe_definition_sha256": head["universe_definition_sha256"],
    }
    row["checkpoint_hash"] = _hash_payload(row, "checkpoint_hash")
    return row


def _build_compact_checkpoint(
    loaded: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    compacted_from_head: Mapping[str, Any],
) -> dict[str, Any]:
    """Materialize one hot-state checkpoint without old cumulative manifests."""

    events = [deepcopy(dict(item)) for item in loaded["events"]]
    manifests = [deepcopy(dict(item)) for item in loaded["manifests"]]
    head_manifest = manifests[-1]
    old_head = validate_segmented_head(compacted_from_head)
    row = {
        **_base_record(COMPACT_CHECKPOINT_RECORD_TYPE),
        "events": events,
        "head_manifest": head_manifest,
        "identity_state": _compact_identity_state(
            {"events": events, "manifests": manifests}
        ),
        "compacted_from_head": deepcopy(old_head),
        "event_count": len(events),
        "manifest_count": len(manifests),
        "head_manifest_id": head_manifest["manifest_id"],
        "head_manifest_hash": head_manifest["manifest_hash"],
        "universe_id": head_manifest["universe_id"],
        "universe_definition_id": head_manifest["universe_definition_id"],
        "universe_definition_version": head_manifest[
            "universe_definition_version"
        ],
        "universe_definition_sha256": head_manifest[
            "universe_definition_sha256"
        ],
    }
    row["checkpoint_hash"] = _hash_payload(row, "checkpoint_hash")
    return row


def _checkpoint_head_manifest(checkpoint: Mapping[str, Any]) -> Mapping[str, Any]:
    if checkpoint["record_type"] == COMPACT_CHECKPOINT_RECORD_TYPE:
        return checkpoint["head_manifest"]
    return checkpoint["manifests"][-1]


def _build_segment(
    *,
    checkpoint_hash: str,
    sequence: int,
    previous_segment_hash: str | None,
    events: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    before_event_count: int,
    before_manifest_count: int,
) -> dict[str, Any]:
    row = {
        **_base_record(SEGMENT_RECORD_TYPE),
        "checkpoint_hash": checkpoint_hash,
        "sequence": sequence,
        "previous_segment_hash": previous_segment_hash,
        "events": [deepcopy(dict(item)) for item in events],
        "manifest": deepcopy(dict(manifest)),
        "before_event_count": before_event_count,
        "after_event_count": before_event_count + len(events),
        "before_manifest_count": before_manifest_count,
        "after_manifest_count": before_manifest_count + 1,
        "previous_manifest_id": manifest["previous_manifest_id"],
        "previous_manifest_hash": manifest["previous_manifest_hash"],
        "head_manifest_id": manifest["manifest_id"],
        "head_manifest_hash": manifest["manifest_hash"],
        "universe_id": manifest["universe_id"],
    }
    row["segment_hash"] = _hash_payload(row, "segment_hash")
    return row


def _build_head(
    checkpoint: Mapping[str, Any],
    segments: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    tip = segments[-1] if segments else checkpoint
    head_manifest = (
        segments[-1]["manifest"]
        if segments
        else _checkpoint_head_manifest(checkpoint)
    )
    row = {
        **_base_record(HEAD_RECORD_TYPE),
        "checkpoint_hash": checkpoint["checkpoint_hash"],
        "tail_segment_hash": None if not segments else segments[-1]["segment_hash"],
        "event_count": tip.get("after_event_count", checkpoint["event_count"]),
        "manifest_count": tip.get("after_manifest_count", checkpoint["manifest_count"]),
        "head_manifest_id": head_manifest["manifest_id"],
        "head_manifest_hash": head_manifest["manifest_hash"],
        "universe_id": head_manifest["universe_id"],
        "universe_definition_id": head_manifest["universe_definition_id"],
        "universe_definition_version": head_manifest["universe_definition_version"],
        "universe_definition_sha256": head_manifest["universe_definition_sha256"],
    }
    row["head_hash"] = _hash_payload(row, "head_hash")
    return row


def build_segmented_ledger_contract(
    legacy_view: Mapping[str, Any], *, checkpoint_manifest_count: int | None = None
) -> dict[str, Any]:
    """Build deterministic in-memory sidecar records from a strict legacy view."""

    loaded = _canonical_legacy_view(legacy_view)
    manifest_count = len(loaded["manifests"])
    checkpoint_count = (
        manifest_count
        if checkpoint_manifest_count is None
        else checkpoint_manifest_count
    )
    if type(checkpoint_count) is not int or not 1 <= checkpoint_count <= manifest_count:
        _fail(
            "segmented_checkpoint_count_invalid",
            "checkpoint_manifest_count must select a committed manifest prefix",
        )
    checkpoint_manifest = loaded["manifests"][checkpoint_count - 1]
    checkpoint_ids = set(checkpoint_manifest["universe_event_ids"])
    checkpoint_loaded = _canonical_legacy_view(
        {
            "events": [item for item in loaded["events"] if item["event_id"] in checkpoint_ids],
            "manifests": loaded["manifests"][:checkpoint_count],
        }
    )
    checkpoint = _build_checkpoint(checkpoint_loaded)
    segments: list[dict[str, Any]] = []
    previous_segment_hash = None
    event_count = len(checkpoint_loaded["events"])
    for index, manifest in enumerate(loaded["manifests"][checkpoint_count:], start=1):
        batch_ids = set(manifest["batch_event_ids"])
        batch_events = [
            item for item in loaded["events"] if item["event_id"] in batch_ids
        ]
        segment = _build_segment(
            checkpoint_hash=checkpoint["checkpoint_hash"],
            sequence=index,
            previous_segment_hash=previous_segment_hash,
            events=batch_events,
            manifest=manifest,
            before_event_count=event_count,
            before_manifest_count=checkpoint_count + index - 1,
        )
        segments.append(segment)
        previous_segment_hash = segment["segment_hash"]
        event_count += len(batch_events)
    head = _build_head(checkpoint, segments)
    return {"head": head, "checkpoint": checkpoint, "segments": segments}


def _validate_record(
    value: Mapping[str, Any], *, fields: frozenset[str], record_type: str, hash_field: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("segmented_record_shape_invalid", f"{record_type} has an invalid shape")
    row = deepcopy(dict(value))
    if (
        type(row["schema_version"]) is not int
        or row["schema_version"] != SCHEMA_VERSION
        or row["record_type"] != record_type
    ):
        _fail("segmented_record_version_invalid", f"unsupported {record_type} record")
    if row["storage_contract"] != STORAGE_CONTRACT:
        _fail("segmented_storage_contract_invalid", "unexpected storage contract")
    _validate_boundary(row)
    supplied = _require_hash(row[hash_field], field=hash_field)
    if supplied != _hash_payload(row, hash_field):
        _fail(f"segmented_{hash_field}_mismatch", f"{hash_field} is incorrect")
    return row


def validate_segmented_head(value: Mapping[str, Any]) -> dict[str, Any]:
    row = _validate_record(
        value, fields=_HEAD_FIELDS, record_type=HEAD_RECORD_TYPE, hash_field="head_hash"
    )
    _require_hash(row["checkpoint_hash"], field="checkpoint_hash")
    _require_hash(row["tail_segment_hash"], field="tail_segment_hash", optional=True)
    _require_count(row["event_count"], field="event_count")
    _require_count(row["manifest_count"], field="manifest_count", positive=True)
    for field in (
        "head_manifest_id",
        "universe_id",
        "universe_definition_id",
        "universe_definition_version",
    ):
        _require_text(row[field], field=field)
    for field in ("head_manifest_hash", "universe_definition_sha256"):
        _require_hash(row[field], field=field)
    return row


def validate_segmented_checkpoint(value: Mapping[str, Any]) -> dict[str, Any]:
    row = _validate_record(
        value,
        fields=_CHECKPOINT_FIELDS,
        record_type=CHECKPOINT_RECORD_TYPE,
        hash_field="checkpoint_hash",
    )
    _require_count(row["event_count"], field="event_count")
    _require_count(row["manifest_count"], field="manifest_count", positive=True)
    if not isinstance(row["events"], list) or not isinstance(row["manifests"], list):
        _fail("segmented_checkpoint_payload_invalid", "checkpoint rows must be arrays")
    if not isinstance(row["identity_state"], Mapping):
        _fail("segmented_checkpoint_payload_invalid", "identity_state must be an object")
    checkpoint_view = _canonical_legacy_view(
        {"events": row["events"], "manifests": row["manifests"]}
    )
    if row != _build_checkpoint(checkpoint_view):
        _fail(
            "segmented_checkpoint_state_mismatch",
            "checkpoint state does not match its strict legacy prefix",
        )
    return row


def _validate_compact_identity_state(
    value: Any,
    *,
    events: Sequence[Mapping[str, Any]],
    head_manifest: Mapping[str, Any],
    manifest_count: int,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _IDENTITY_STATE_FIELDS:
        _fail(
            "segmented_compact_identity_state_invalid",
            "compact identity_state has an invalid shape",
        )
    state = deepcopy(dict(value))
    manifest_identities = state["manifest_identities"]
    if (
        not isinstance(manifest_identities, list)
        or len(manifest_identities) != manifest_count
    ):
        _fail(
            "segmented_compact_identity_state_invalid",
            "manifest identity count must equal logical manifest_count",
        )
    seen_manifest_ids: set[str] = set()
    seen_batch_ids: set[str] = set()
    introduced_source_ids: set[str] = set()
    introduced_evidence_ids: set[str] = set()
    for item in manifest_identities:
        if not isinstance(item, Mapping) or set(item) != {
            "manifest_id",
            "manifest_hash",
            "semantic_hash",
            "event_batch_id",
            "introduced_source_contract_ids",
            "introduced_evidence_record_ids",
        }:
            _fail(
                "segmented_compact_identity_state_invalid",
                "manifest identity entries have an invalid shape",
            )
        manifest_id = _require_text(item["manifest_id"], field="manifest_id")
        batch_id = _require_text(item["event_batch_id"], field="event_batch_id")
        _require_hash(item["manifest_hash"], field="manifest_hash")
        _require_hash(item["semantic_hash"], field="semantic_hash")
        for field in (
            "introduced_source_contract_ids",
            "introduced_evidence_record_ids",
        ):
            identifiers = item[field]
            if (
                not isinstance(identifiers, list)
                or any(
                    not isinstance(identifier, str) or not identifier
                    for identifier in identifiers
                )
                or identifiers != sorted(set(identifiers))
            ):
                _fail(
                    "segmented_compact_identity_state_invalid",
                    f"{field} must be a sorted unique string array",
                )
        new_source_ids = set(item["introduced_source_contract_ids"])
        new_evidence_ids = set(item["introduced_evidence_record_ids"])
        if (
            introduced_source_ids.intersection(new_source_ids)
            or introduced_evidence_ids.intersection(new_evidence_ids)
        ):
            _fail(
                "segmented_compact_identity_state_invalid",
                "registry identities may be introduced by only one manifest",
            )
        introduced_source_ids.update(new_source_ids)
        introduced_evidence_ids.update(new_evidence_ids)
        if manifest_id in seen_manifest_ids or batch_id in seen_batch_ids:
            _fail(
                "segmented_compact_identity_state_invalid",
                "manifest and event_batch identities must be unique",
            )
        seen_manifest_ids.add(manifest_id)
        seen_batch_ids.add(batch_id)
    last_identity = manifest_identities[-1]
    if any(
        last_identity[field] != head_manifest[field]
        for field in (
            "manifest_id",
            "manifest_hash",
            "semantic_hash",
            "event_batch_id",
        )
    ):
        _fail(
            "segmented_compact_identity_state_invalid",
            "last manifest identity must bind the exact head manifest",
        )

    clock_bindings = state["clock_bindings"]
    if not isinstance(clock_bindings, Mapping):
        _fail(
            "segmented_compact_identity_state_invalid",
            "clock_bindings must be an object",
        )
    normalized_clocks: dict[str, dict[str, str]] = {}
    for clock_id, binding in clock_bindings.items():
        identifier = _require_text(clock_id, field="clock_bindings key")
        if not isinstance(binding, Mapping) or set(binding) != {
            "semantic_hash",
            "record_hash",
            "calendar_evidence_id",
            "calendar_evidence_record_hash",
        }:
            _fail(
                "segmented_compact_identity_state_invalid",
                "clock binding entries have an invalid shape",
            )
        normalized_clocks[identifier] = {
            "semantic_hash": _require_hash(
                binding["semantic_hash"], field="clock semantic_hash"
            ),
            "record_hash": _require_hash(
                binding["record_hash"], field="clock record_hash"
            ),
            "calendar_evidence_id": _require_text(
                binding["calendar_evidence_id"], field="calendar_evidence_id"
            ),
            "calendar_evidence_record_hash": _require_hash(
                binding["calendar_evidence_record_hash"],
                field="calendar_evidence_record_hash",
            ),
        }
    if dict(clock_bindings) != dict(sorted(normalized_clocks.items())):
        _fail(
            "segmented_compact_identity_state_invalid",
            "clock bindings must be canonical and identity-sorted",
        )
    for prefix in ("session_clock", "effective_session_clock"):
        clock_id = head_manifest[f"{prefix}_id"]
        if normalized_clocks.get(clock_id) != {
            "semantic_hash": head_manifest[f"{prefix}_hash"],
            "record_hash": head_manifest[f"{prefix}_record_hash"],
            "calendar_evidence_id": head_manifest[
                f"{prefix}_calendar_evidence_id"
            ],
            "calendar_evidence_record_hash": head_manifest[
                f"{prefix}_calendar_evidence_record_hash"
            ],
        }:
            _fail(
                "segmented_compact_identity_state_invalid",
                "head manifest clocks must resolve in compact history",
            )

    current = _identity_state({"events": events, "manifests": [head_manifest]})
    for field in ("source_contract_registry", "evidence_record_registry"):
        if not isinstance(state[field], Mapping):
            _fail(
                "segmented_compact_identity_state_invalid",
                f"{field} must be an object",
            )
    if (
        introduced_source_ids != set(state["source_contract_registry"])
        or introduced_evidence_ids != set(state["evidence_record_registry"])
    ):
        _fail(
            "segmented_compact_identity_state_invalid",
            "manifest registry introductions must cover the current registries",
        )
    for field in (
        "event_identities",
        "source_contract_registry",
        "evidence_record_registry",
        "rule_bindings",
        "mapping_bindings",
        "event_chain_heads",
        "memberships",
        "membership_snapshot_sha256",
        "pending_future_event_ids",
    ):
        if state[field] != current[field]:
            _fail(
                "segmented_compact_checkpoint_state_mismatch",
                f"compact {field} does not match the exact current state",
            )
    return state


def validate_segmented_compact_checkpoint(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    row = _validate_record(
        value,
        fields=_COMPACT_CHECKPOINT_FIELDS,
        record_type=COMPACT_CHECKPOINT_RECORD_TYPE,
        hash_field="checkpoint_hash",
    )
    _require_count(row["event_count"], field="event_count")
    _require_count(row["manifest_count"], field="manifest_count", positive=True)
    if not isinstance(row["events"], list) or not isinstance(
        row["head_manifest"], Mapping
    ):
        _fail(
            "segmented_compact_checkpoint_payload_invalid",
            "compact checkpoint needs event rows and one head manifest",
        )
    head_manifest = _validate_manifest_shape(row["head_manifest"])
    try:
        records, _ = _validate_manifest_population_bindings(
            head_manifest, row["events"]
        )
        _validate_manifest_research_pit(head_manifest, records)
    except (V2UniverseLedgerError, V2ContractValidationError) as exc:
        raise V2UniverseSegmentError(exc.code, exc.detail) from exc
    validated_by_id = {event.event_id: event.to_dict() for event in records}
    events: list[dict[str, Any]] = []
    for raw in row["events"]:
        event_id = raw.get("event_id") if isinstance(raw, Mapping) else None
        validated = validated_by_id.get(event_id)
        if validated is None or raw != validated:
            _fail(
                "segmented_compact_checkpoint_state_mismatch",
                "compact event rows must preserve exact validated records",
            )
        events.append(validated)
    if (
        len(validated_by_id) != len(events)
        or row["event_count"] != len(events)
    ):
        _fail(
            "segmented_compact_checkpoint_state_mismatch",
            "compact event population is not exact",
        )
    state = _validate_compact_identity_state(
        row["identity_state"],
        events=events,
        head_manifest=head_manifest,
        manifest_count=row["manifest_count"],
    )
    old_head = validate_segmented_head(row["compacted_from_head"])
    for field in (
        "event_count",
        "manifest_count",
        "head_manifest_id",
        "head_manifest_hash",
        "universe_id",
        "universe_definition_id",
        "universe_definition_version",
        "universe_definition_sha256",
        *_BOUNDARY,
    ):
        if old_head[field] != row[field]:
            _fail(
                "segmented_compact_lineage_mismatch",
                f"compacted predecessor disagrees on {field}",
            )
    if old_head["checkpoint_hash"] == row["checkpoint_hash"]:
        _fail(
            "segmented_compact_lineage_cycle",
            "compact lineage cannot self-reference",
        )
    if (
        row["head_manifest_id"] != head_manifest["manifest_id"]
        or row["head_manifest_hash"] != head_manifest["manifest_hash"]
        or row["universe_id"] != head_manifest["universe_id"]
        or row["universe_definition_id"]
        != head_manifest["universe_definition_id"]
        or row["universe_definition_version"]
        != head_manifest["universe_definition_version"]
        or row["universe_definition_sha256"]
        != head_manifest["universe_definition_sha256"]
        or state["membership_snapshot_sha256"]
        != head_manifest["membership_snapshot_sha256"]
    ):
        _fail(
            "segmented_compact_checkpoint_state_mismatch",
            "compact tip fields do not match the head manifest",
        )
    return row


def _validate_checkpoint_record(value: Mapping[str, Any]) -> dict[str, Any]:
    record_type = value.get("record_type") if isinstance(value, Mapping) else None
    if record_type == CHECKPOINT_RECORD_TYPE:
        return validate_segmented_checkpoint(value)
    if record_type == COMPACT_CHECKPOINT_RECORD_TYPE:
        return validate_segmented_compact_checkpoint(value)
    _fail("segmented_checkpoint_record_type_invalid", "unknown checkpoint record type")


def validate_segmented_segment(value: Mapping[str, Any]) -> dict[str, Any]:
    row = _validate_record(
        value,
        fields=_SEGMENT_FIELDS,
        record_type=SEGMENT_RECORD_TYPE,
        hash_field="segment_hash",
    )
    _require_hash(row["checkpoint_hash"], field="checkpoint_hash")
    _require_hash(row["previous_segment_hash"], field="previous_segment_hash", optional=True)
    _require_count(row["sequence"], field="sequence", positive=True)
    for field in (
        "before_event_count",
        "after_event_count",
        "before_manifest_count",
        "after_manifest_count",
    ):
        _require_count(row[field], field=field)
    if not isinstance(row["events"], list) or not isinstance(row["manifest"], Mapping):
        _fail(
            "segmented_segment_payload_invalid",
            "segment must contain event rows and one manifest",
        )
    if row["after_event_count"] != row["before_event_count"] + len(row["events"]):
        _fail("segmented_segment_count_mismatch", "segment event counts are inconsistent")
    if row["after_manifest_count"] != row["before_manifest_count"] + 1:
        _fail("segmented_segment_count_mismatch", "segment must add exactly one manifest")
    try:
        manifest = _validate_manifest_shape(row["manifest"])
        event_records = [validate_universe_event(item) for item in row["events"]]
    except (V2UniverseLedgerError, V2ContractValidationError) as exc:
        raise V2UniverseSegmentError(exc.code, exc.detail) from exc
    event_ids = [item.event_id for item in event_records]
    if (
        len(event_ids) != len(set(event_ids))
        or sorted(event_ids) != manifest["batch_event_ids"]
    ):
        _fail(
            "segmented_event_population_mismatch",
            "segment events must equal the manifest batch_event_ids exactly",
        )
    if (
        row["previous_manifest_id"] != manifest["previous_manifest_id"]
        or row["previous_manifest_hash"] != manifest["previous_manifest_hash"]
        or row["head_manifest_id"] != manifest["manifest_id"]
        or row["head_manifest_hash"] != manifest["manifest_hash"]
        or row["universe_id"] != manifest["universe_id"]
    ):
        _fail(
            "segmented_segment_state_mismatch",
            "segment identities do not match its exact manifest",
        )
    for event in event_records:
        if (
            event.event_batch_id != manifest["event_batch_id"]
            or event.universe_id != manifest["universe_id"]
            or event.run_id != manifest["run_id"]
            or event.session_clock_id != manifest["session_clock_id"]
            or event.session_clock_hash != manifest["session_clock_hash"]
            or event.session_clock_record_hash
            != manifest["session_clock_record_hash"]
            or event.run_date != manifest["run_date"]
            or event.calendar_session_id != manifest["calendar_session_id"]
            or event.effective_session_clock_id
            != manifest["effective_session_clock_id"]
            or event.effective_session_clock_hash
            != manifest["effective_session_clock_hash"]
            or event.effective_session_clock_record_hash
            != manifest["effective_session_clock_record_hash"]
            or event.effective_session_id != manifest["effective_session_id"]
        ):
            _fail(
                "segmented_segment_event_binding_mismatch",
                "segment events must bind the manifest batch, universe, and clocks",
            )
    return row


def _storage_directory(root: str | Path, name: str) -> Path:
    root_path = Path(root)
    directory = root_path / name
    if os.path.lexists(directory):
        if directory.is_symlink():
            _fail(
                "segmented_storage_directory_invalid",
                f"{name} cannot be a symbolic link",
            )
        try:
            escaped = directory.resolve() != root_path.resolve() / name
        except (OSError, RuntimeError) as exc:
            raise V2UniverseSegmentError(
                "segmented_storage_directory_invalid",
                f"cannot resolve {name} storage directory: {exc}",
            ) from exc
        if escaped or not directory.is_dir():
            _fail(
                "segmented_storage_directory_invalid",
                f"{name} must be a real directory inside the configured root",
            )
    return directory


def _validate_segmented_lock_path(path: Path) -> None:
    if not os.path.lexists(path):
        return
    if path.is_symlink():
        _fail(
            "segmented_lock_path_invalid",
            "HEAD.json.lock cannot be a symbolic link",
        )
    try:
        stat = path.stat()
    except OSError as exc:
        raise V2UniverseSegmentError(
            "segmented_lock_path_invalid",
            f"cannot inspect segmented lock path: {exc}",
        ) from exc
    if not path.is_file() or stat.st_nlink != 1:
        _fail(
            "segmented_lock_path_invalid",
            "HEAD.json.lock must be one real, singly linked file",
        )


def segmented_record_path(root: str | Path, kind: str, record_hash: str) -> Path:
    digest = _require_hash(record_hash, field=f"{kind}_hash")
    if kind == "checkpoint":
        return _storage_directory(root, "checkpoints") / f"{digest}.json"
    if kind == "segment":
        return _storage_directory(root, "segments") / f"{digest}.json"
    _fail("segmented_record_kind_invalid", "kind must be checkpoint or segment")


def _canonical_record_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return (canonical_json(value) + "\n").encode("utf-8")
    except V2ContractValidationError as exc:
        raise V2UniverseSegmentError(exc.code, exc.detail) from exc


def _publish_immutable_record(
    path: Path, value: Mapping[str, Any], *, role: str
) -> bool:
    """Create one content-addressed record without ever replacing its path."""

    payload = _canonical_record_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
            return False
        except FileExistsError:
            if path.is_symlink() or not path.is_file():
                _fail(
                    f"segmented_{role}_collision",
                    f"immutable {role} path must be one real file: {path}",
                )
            try:
                existing = path.read_bytes()
            except OSError as exc:
                raise V2UniverseSegmentError(
                    f"segmented_{role}_collision",
                    f"cannot verify existing immutable {role} {path}: {exc}",
                ) from exc
            if existing != payload:
                _fail(
                    f"segmented_{role}_collision",
                    f"immutable {role} path already contains different bytes: {path}",
                )
            return True
        except OSError as exc:
            raise V2UniverseSegmentError(
                f"segmented_{role}_publish_failed",
                f"cannot publish immutable {role} {path}: {exc}",
            ) from exc
    finally:
        if temporary is not None:
            try:
                Path(temporary).unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def _validate_bootstrap_recovery_surface(
    root: Path, checkpoint_path: Path, checkpoint: Mapping[str, Any]
) -> None:
    """Allow only a virgin root or the exact orphan from this first commit."""

    checkpoints = sorted(_storage_directory(root, "checkpoints").glob("*.json"))
    segments = sorted(_storage_directory(root, "segments").glob("*.json"))
    if not checkpoints and not segments:
        return
    expected = _canonical_record_bytes(checkpoint)
    try:
        exact_orphan = (
            not segments
            and checkpoints == [checkpoint_path]
            and not checkpoint_path.is_symlink()
            and checkpoint_path.read_bytes() == expected
        )
    except OSError:
        exact_orphan = False
    if not exact_orphan:
        _fail(
            "segmented_bootstrap_orphan_conflict",
            "missing HEAD is recoverable only with the one exact planned checkpoint and no segments",
        )


def _assert_head_identity(path: Path, expected_bytes: bytes | None) -> None:
    try:
        present = os.path.lexists(path)
        actual = path.read_bytes() if present else None
    except OSError as exc:
        raise V2UniverseSegmentError(
            "segmented_stale_head", f"cannot verify prior HEAD identity: {exc}"
        ) from exc
    if actual != expected_bytes:
        _fail(
            "segmented_stale_head",
            "HEAD changed after this transaction read its predecessor",
        )


def _atomic_publish_head(
    path: Path, value: Mapping[str, Any], *, expected_bytes: bytes | None
) -> None:
    """Publish exact LF bytes only after a last predecessor identity check."""

    payload = _canonical_record_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _assert_head_identity(path, expected_bytes)
        try:
            _replace_with_retry(temporary, path)
        except OSError as exc:
            raise V2UniverseSegmentError(
                "segmented_head_write_failed", f"cannot publish HEAD {path}: {exc}"
            ) from exc
        temporary = None
    finally:
        if temporary is not None:
            try:
                Path(temporary).unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def _read_json(path: Path, *, role: str) -> dict[str, Any]:
    if path.is_symlink():
        _fail(
            f"segmented_{role}_invalid",
            f"referenced {role} cannot be a symbolic link: {path}",
        )
    if not path.is_file():
        _fail(f"segmented_{role}_missing", f"referenced {role} is missing: {path}")

    def reject_constant(value: str):
        raise ValueError(f"non-finite JSON constant {value}")

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"non-finite JSON number {value}")
        return parsed

    try:
        raw_bytes = path.read_bytes()
        raw_text = raw_bytes.decode("utf-8")
        value = json.loads(
            raw_text,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
        canonical_bytes = (canonical_json(value) + "\n").encode("utf-8")
    except (
        OSError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
        V2ContractValidationError,
    ) as exc:
        raise V2UniverseSegmentError(
            f"segmented_{role}_invalid", f"cannot read {role} {path}: {exc}"
        ) from exc
    if not isinstance(value, Mapping):
        _fail(f"segmented_{role}_invalid", f"{role} must be a JSON object")
    if raw_bytes != canonical_bytes:
        _fail(
            f"segmented_{role}_noncanonical_bytes",
            f"{role} must use the exact canonical UTF-8 serialization",
        )
    return dict(value)


def _clock_registry_from_identity_state(
    identity_state: Mapping[str, Any],
) -> dict[str, tuple[str, str, str, str]]:
    return {
        clock_id: (
            binding["semantic_hash"],
            binding["record_hash"],
            binding["calendar_evidence_id"],
            binding["calendar_evidence_record_hash"],
        )
        for clock_id, binding in identity_state["clock_bindings"].items()
    }


def _load_generation(
    root: Path,
    head: Mapping[str, Any],
    *,
    head_target: Path | None,
    seen_checkpoints: set[str],
) -> tuple[dict[str, list[dict[str, Any]]], set[Path], dict[str, Any]]:
    head = validate_segmented_head(head)
    if head["checkpoint_hash"] in seen_checkpoints:
        _fail(
            "segmented_compact_lineage_cycle",
            "checkpoint lineage contains a cycle",
        )
    seen_checkpoints.add(head["checkpoint_hash"])
    checkpoint_path = segmented_record_path(root, "checkpoint", head["checkpoint_hash"])
    checkpoint = _validate_checkpoint_record(
        _read_json(checkpoint_path, role="checkpoint")
    )
    if checkpoint["checkpoint_hash"] != head["checkpoint_hash"]:
        _fail("segmented_checkpoint_binding_mismatch", "HEAD binds another checkpoint")

    reachable = {checkpoint_path.resolve()}
    if head_target is not None:
        reachable.add(head_target.resolve())
    compact = checkpoint["record_type"] == COMPACT_CHECKPOINT_RECORD_TYPE
    archived_reachable: set[Path] = set()
    if compact:
        events = deepcopy(checkpoint["events"])
        manifests = [deepcopy(checkpoint["head_manifest"])]
        clock_registry = _clock_registry_from_identity_state(
            checkpoint["identity_state"]
        )
        manifest_identities = checkpoint["identity_state"]["manifest_identities"]
        seen_manifest_ids = {
            item["manifest_id"] for item in manifest_identities
        }
        seen_event_batch_ids = {
            item["event_batch_id"] for item in manifest_identities
        }
    else:
        events = deepcopy(checkpoint["events"])
        manifests = deepcopy(checkpoint["manifests"])
        seen_manifest_ids = {item["manifest_id"] for item in manifests}
        seen_event_batch_ids = {item["event_batch_id"] for item in manifests}
        clock_registry: dict[str, tuple[str, str, str, str]] = {}
        for manifest in manifests:
            try:
                _extend_clock_binding_registry(manifest, clock_registry)
            except V2UniverseLedgerError as exc:
                raise V2UniverseSegmentError(exc.code, exc.detail) from exc

    reversed_segments: list[dict[str, Any]] = []
    current_hash = head["tail_segment_hash"]
    seen: set[str] = set()
    while current_hash is not None:
        if current_hash in seen:
            _fail("segmented_segment_cycle", "segment chain contains a cycle")
        seen.add(current_hash)
        segment_path = segmented_record_path(root, "segment", current_hash)
        segment = validate_segmented_segment(_read_json(segment_path, role="segment"))
        if segment["segment_hash"] != current_hash:
            _fail("segmented_segment_binding_mismatch", "segment filename/hash binding is wrong")
        if segment["checkpoint_hash"] != checkpoint["checkpoint_hash"]:
            _fail("segmented_checkpoint_binding_mismatch", "segment binds another checkpoint")
        reversed_segments.append(segment)
        reachable.add(segment_path.resolve())
        current_hash = segment["previous_segment_hash"]
    segments = list(reversed(reversed_segments))
    previous_hash = None
    for sequence, segment in enumerate(segments, start=1):
        previous_manifest = manifests[-1]
        manifest = segment["manifest"]
        if (
            segment["sequence"] != sequence
            or segment["previous_segment_hash"] != previous_hash
            or segment["before_event_count"] != len(events)
            or segment["before_manifest_count"]
            != checkpoint["manifest_count"] + sequence - 1
            or segment["previous_manifest_id"] != previous_manifest["manifest_id"]
            or segment["previous_manifest_hash"] != previous_manifest["manifest_hash"]
        ):
            _fail("segmented_segment_chain_mismatch", "segment predecessor/count chain is invalid")
        expected = _build_segment(
            checkpoint_hash=checkpoint["checkpoint_hash"],
            sequence=sequence,
            previous_segment_hash=previous_hash,
            events=segment["events"],
            manifest=segment["manifest"],
            before_event_count=len(events),
            before_manifest_count=checkpoint["manifest_count"] + sequence - 1,
        )
        if segment != expected:
            _fail(
                "segmented_segment_state_mismatch",
                "segment metadata does not match its transaction",
            )
        combined_events = [*events, *deepcopy(segment["events"])]
        if manifest["manifest_id"] in seen_manifest_ids:
            _fail(
                "duplicate_physical_manifest",
                "manifest_id appears more than once across compact history and tail",
            )
        if manifest["event_batch_id"] in seen_event_batch_ids:
            _fail(
                "duplicate_event_batch_id",
                "event_batch_id appears more than once across compact history and tail",
            )
        try:
            _validate_manifest_event_bindings(
                manifest, combined_events, previous_manifest
            )
            _extend_clock_binding_registry(manifest, clock_registry)
        except (V2UniverseLedgerError, V2ContractValidationError) as exc:
            raise V2UniverseSegmentError(exc.code, exc.detail) from exc
        events = combined_events
        manifests.append(deepcopy(manifest))
        seen_manifest_ids.add(manifest["manifest_id"])
        seen_event_batch_ids.add(manifest["event_batch_id"])
        previous_hash = segment["segment_hash"]

    if not compact:
        reconstructed = _canonical_legacy_view(
            {"events": events, "manifests": manifests}
        )
    else:
        reconstructed = {"events": events, "manifests": manifests}
    final_manifest = reconstructed["manifests"][-1]
    if (
        head["tail_segment_hash"] != previous_hash
        or head["event_count"] != len(reconstructed["events"])
        or head["manifest_count"] != checkpoint["manifest_count"] + len(segments)
        or head["head_manifest_id"] != final_manifest["manifest_id"]
        or head["head_manifest_hash"] != final_manifest["manifest_hash"]
        or head["universe_id"] != final_manifest["universe_id"]
        or head["universe_definition_id"] != final_manifest["universe_definition_id"]
        or head["universe_definition_version"] != final_manifest["universe_definition_version"]
        or head["universe_definition_sha256"] != final_manifest["universe_definition_sha256"]
    ):
        _fail("segmented_head_state_mismatch", "HEAD does not bind the reconstructed ledger tip")
    return reconstructed, reachable, {
        "head": head,
        "checkpoint": checkpoint,
        "segments": segments,
        "compact": compact,
        "archived_reachable": archived_reachable,
    }


def _load_exact_generations(
    root: Path,
    head: Mapping[str, Any],
    *,
    head_target: Path,
) -> tuple[dict[str, list[dict[str, Any]]], set[Path], dict[str, Any]]:
    """Iteratively rebuild exact history across compact generations."""

    generation_heads: list[dict[str, Any]] = []
    cursor = validate_segmented_head(head)
    seen: set[str] = set()
    while True:
        checkpoint_hash = cursor["checkpoint_hash"]
        if checkpoint_hash in seen:
            _fail(
                "segmented_compact_lineage_cycle",
                "checkpoint lineage contains a cycle",
            )
        seen.add(checkpoint_hash)
        checkpoint_path = segmented_record_path(
            root, "checkpoint", checkpoint_hash
        )
        checkpoint = _validate_checkpoint_record(
            _read_json(checkpoint_path, role="checkpoint")
        )
        if checkpoint["checkpoint_hash"] != checkpoint_hash:
            _fail(
                "segmented_checkpoint_binding_mismatch",
                "archival HEAD binds another checkpoint",
            )
        generation_heads.append(cursor)
        if checkpoint["record_type"] != COMPACT_CHECKPOINT_RECORD_TYPE:
            break
        cursor = validate_segmented_head(checkpoint["compacted_from_head"])

    exact: dict[str, list[dict[str, Any]]] | None = None
    reachable: set[Path] = set()
    current_reachable: set[Path] = set()
    current_metadata: dict[str, Any] | None = None
    for generation_index, generation_head in enumerate(
        reversed(generation_heads)
    ):
        is_current = generation_index == len(generation_heads) - 1
        view, generation_reachable, metadata = _load_generation(
            root,
            generation_head,
            head_target=head_target if is_current else None,
            seen_checkpoints=set(),
        )
        reachable.update(generation_reachable)
        if exact is None:
            if metadata["compact"]:
                _fail(
                    "segmented_compact_lineage_missing",
                    "compact lineage must terminate at a full checkpoint",
                )
            exact = view
        else:
            checkpoint = metadata["checkpoint"]
            if (
                not metadata["compact"]
                or checkpoint["events"] != exact["events"]
                or checkpoint["manifest_count"] != len(exact["manifests"])
                or checkpoint["head_manifest"] != exact["manifests"][-1]
                or checkpoint["identity_state"] != _compact_identity_state(exact)
            ):
                _fail(
                    "segmented_compact_lineage_mismatch",
                    "archived generation does not reconstruct the compact base",
                )
            for segment in metadata["segments"]:
                exact["events"].extend(deepcopy(segment["events"]))
                exact["manifests"].append(deepcopy(segment["manifest"]))
            if (
                exact["events"] != view["events"]
                or exact["manifests"][-1] != view["manifests"][-1]
                or len(exact["manifests"]) != metadata["head"]["manifest_count"]
            ):
                _fail(
                    "segmented_compact_lineage_mismatch",
                    "compact generation tail does not extend archived history exactly",
                )
        if is_current:
            current_reachable = generation_reachable
            current_metadata = metadata

    if exact is None or current_metadata is None:
        _fail("segmented_compact_lineage_missing", "no committed generation exists")
    reconstructed = _canonical_legacy_view(exact)
    current_metadata["archived_reachable"] = reachable - current_reachable
    return reconstructed, reachable, current_metadata


def _load_store(
    root: Path,
    head_path: str | Path,
    *,
    reconstruct_archived: bool,
) -> tuple[dict[str, list[dict[str, Any]]], set[Path], dict[str, Any]]:
    head_target = Path(head_path)
    if not head_target.is_absolute():
        head_target = root / head_target
    head = validate_segmented_head(_read_json(head_target, role="head"))
    if reconstruct_archived:
        return _load_exact_generations(
            root,
            head,
            head_target=head_target,
        )
    return _load_generation(
        root,
        head,
        head_target=head_target,
        seen_checkpoints=set(),
    )


def _load_reachable_store(
    root: Path, head_path: str | Path
) -> tuple[dict[str, list[dict[str, Any]]], set[Path]]:
    loaded, reachable, _ = _load_store(
        root, head_path, reconstruct_archived=True
    )
    return loaded, reachable


def _load_hot_store(
    root: Path, head_path: str | Path
) -> tuple[dict[str, list[dict[str, Any]]], set[Path], dict[str, Any]]:
    return _load_store(root, head_path, reconstruct_archived=False)


def load_segmented_v2_universe_ledger(
    root: str | Path, *, head_path: str | Path = "HEAD.json"
) -> dict[str, list[dict[str, Any]]]:
    """Return exact legacy history, following compact archival lineage if needed."""

    loaded, _ = _load_reachable_store(Path(root), head_path)
    return loaded


def load_segmented_v2_universe_state(
    root: str | Path, *, head_path: str | Path = "HEAD.json"
) -> dict[str, Any]:
    """Load current hot state without traversing superseded generations."""

    loaded, _, metadata = _load_hot_store(Path(root), head_path)
    head = metadata["head"]
    return {
        "events": deepcopy(loaded["events"]),
        "head_manifest": deepcopy(loaded["manifests"][-1]),
        "event_count": head["event_count"],
        "manifest_count": head["manifest_count"],
        "checkpoint_hash": head["checkpoint_hash"],
        "tail_segment_hash": head["tail_segment_hash"],
        "current_generation_manifest_count": len(loaded["manifests"]),
        "authority": "research_only",
        "trade_enabled": False,
    }


def bootstrap_segmented_v2_universe_ledger(
    root: str | Path,
    events: Iterable[Mapping[str, Any] | UniverseEvent],
    manifest: Mapping[str, Any],
    *,
    run_clock: Mapping[str, Any] | SessionClock,
    effective_clock: Mapping[str, Any] | SessionClock,
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    run_calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    run_calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    run_calendar_source_contract: Mapping[str, Any] | SourceContract,
    effective_calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    effective_calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    effective_calendar_source_contract: Mapping[str, Any] | SourceContract,
    lock_timeout_seconds: float = _LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Guard and publish the first transaction as one full checkpoint."""

    prepared = _prepare_v2_universe_batch_append(
        events,
        manifest,
        run_clock=run_clock,
        effective_clock=effective_clock,
        evidence_records=evidence_records,
        source_contracts=source_contracts,
        run_calendar_sessions=run_calendar_sessions,
        run_calendar_evidence=run_calendar_evidence,
        run_calendar_source_contract=run_calendar_source_contract,
        effective_calendar_sessions=effective_calendar_sessions,
        effective_calendar_evidence=effective_calendar_evidence,
        effective_calendar_source_contract=effective_calendar_source_contract,
    )
    timeout = _validated_lock_timeout(lock_timeout_seconds)
    root_path = Path(root)
    head_path = root_path / "HEAD.json"
    lock_path = root_path / "HEAD.json.lock"
    _validate_segmented_lock_path(lock_path)
    with _exclusive_ledger_lock(lock_path, timeout_seconds=timeout):
        if os.path.lexists(head_path):
            current_head = validate_segmented_head(_read_json(head_path, role="head"))
            current_head_bytes = _canonical_record_bytes(current_head)
            current, _ = _load_reachable_store(root_path, "HEAD.json")
            _assert_head_identity(head_path, current_head_bytes)
            plan = _classify_v2_universe_batch_append(current, prepared)
            if plan["status"] == "duplicate":
                _assert_head_identity(head_path, current_head_bytes)
                return {
                    "status": "duplicate",
                    "rows_written": 0,
                    "checkpoint_reused": True,
                    "checkpoint_hash": current_head["checkpoint_hash"],
                    "head_hash": current_head["head_hash"],
                    "event_count": len(current["events"]),
                    "manifest_count": len(current["manifests"]),
                    "path": str(head_path),
                }
            _fail(
                "segmented_bootstrap_conflict",
                "segmented store is already initialized with another HEAD",
            )

        plan = _classify_v2_universe_batch_append(
            {"events": [], "manifests": []}, prepared
        )
        if plan["status"] != "append":
            _fail("segmented_bootstrap_invalid", "first transaction was not appendable")
        expected_view = {"events": plan["events"], "manifests": plan["manifests"]}
        contract = build_segmented_ledger_contract(expected_view)
        checkpoint = validate_segmented_checkpoint(contract["checkpoint"])
        head = validate_segmented_head(contract["head"])
        checkpoint_path = segmented_record_path(
            root_path, "checkpoint", checkpoint["checkpoint_hash"]
        )
        _validate_bootstrap_recovery_surface(root_path, checkpoint_path, checkpoint)
        checkpoint_reused = _publish_immutable_record(
            checkpoint_path, checkpoint, role="checkpoint"
        )
        if validate_segmented_checkpoint(
            _read_json(checkpoint_path, role="checkpoint")
        ) != checkpoint:
            _fail(
                "segmented_checkpoint_publish_mismatch",
                "published checkpoint differs from the planned record",
            )
        _atomic_publish_head(head_path, head, expected_bytes=None)
        committed = load_segmented_v2_universe_ledger(root_path)
        if committed != expected_view:
            _fail(
                "segmented_publish_verification_failed",
                "published bootstrap does not reconstruct the planned ledger",
            )
        return {
            "status": "bootstrapped",
            "rows_written": 1 if checkpoint_reused else 2,
            "checkpoint_reused": checkpoint_reused,
            "checkpoint_hash": checkpoint["checkpoint_hash"],
            "head_hash": head["head_hash"],
            "event_count": len(committed["events"]),
            "manifest_count": len(committed["manifests"]),
            "path": str(head_path),
        }


def append_segmented_v2_universe_batch(
    root: str | Path,
    events: Iterable[Mapping[str, Any] | UniverseEvent],
    manifest: Mapping[str, Any],
    *,
    run_clock: Mapping[str, Any] | SessionClock,
    effective_clock: Mapping[str, Any] | SessionClock,
    evidence_records: Sequence[Mapping[str, Any] | EvidenceRecord],
    source_contracts: Sequence[Mapping[str, Any] | SourceContract],
    run_calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    run_calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    run_calendar_source_contract: Mapping[str, Any] | SourceContract,
    effective_calendar_sessions: Sequence[Mapping[str, Any] | CalendarSession],
    effective_calendar_evidence: Mapping[str, Any] | EvidenceRecord,
    effective_calendar_source_contract: Mapping[str, Any] | SourceContract,
    lock_timeout_seconds: float = _LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Append one guarded legacy transaction as one immutable segment."""

    prepared = _prepare_v2_universe_batch_append(
        events,
        manifest,
        run_clock=run_clock,
        effective_clock=effective_clock,
        evidence_records=evidence_records,
        source_contracts=source_contracts,
        run_calendar_sessions=run_calendar_sessions,
        run_calendar_evidence=run_calendar_evidence,
        run_calendar_source_contract=run_calendar_source_contract,
        effective_calendar_sessions=effective_calendar_sessions,
        effective_calendar_evidence=effective_calendar_evidence,
        effective_calendar_source_contract=effective_calendar_source_contract,
    )
    timeout = _validated_lock_timeout(lock_timeout_seconds)
    root_path = Path(root)
    head_path = root_path / "HEAD.json"
    lock_path = root_path / "HEAD.json.lock"
    _validate_segmented_lock_path(lock_path)
    with _exclusive_ledger_lock(lock_path, timeout_seconds=timeout):
        old_head = validate_segmented_head(_read_json(head_path, role="head"))
        old_head_bytes = _canonical_record_bytes(old_head)
        _assert_head_identity(head_path, old_head_bytes)
        loaded, _, metadata = _load_hot_store(root_path, "HEAD.json")
        _assert_head_identity(head_path, old_head_bytes)
        checkpoint = metadata["checkpoint"]
        if metadata["compact"]:
            historical = checkpoint["identity_state"]["manifest_identities"]
            proposed_manifest = prepared["manifest"]
            clock_registry = _clock_registry_from_identity_state(
                checkpoint["identity_state"]
            )
            try:
                _extend_clock_binding_registry(
                    proposed_manifest, clock_registry
                )
            except V2UniverseLedgerError as exc:
                raise V2UniverseSegmentError(exc.code, exc.detail) from exc
            window_manifest_ids = {
                item["manifest_id"] for item in loaded["manifests"][1:]
            }
            historical_by_id = {
                item["manifest_id"]: item for item in historical
            }
            historical_index_by_id = {
                item["manifest_id"]: index
                for index, item in enumerate(historical)
            }
            historical_identity = historical_by_id.get(
                proposed_manifest["manifest_id"]
            )
            if proposed_manifest["manifest_id"] in window_manifest_ids:
                plan = _classify_v2_universe_batch_append(loaded, prepared)
            elif historical_identity is not None:
                historical_index = historical_index_by_id[
                    proposed_manifest["manifest_id"]
                ]
                previous_identities = historical[:historical_index]
                if previous_identities:
                    previous_source_ids = {
                        identifier
                        for identity in previous_identities
                        for identifier in identity[
                            "introduced_source_contract_ids"
                        ]
                    }
                    previous_evidence_ids = {
                        identifier
                        for identity in previous_identities
                        for identifier in identity[
                            "introduced_evidence_record_ids"
                        ]
                    }
                    registry_previous = {
                        "source_contract_registry": {
                            identifier: checkpoint["identity_state"][
                                "source_contract_registry"
                            ][identifier]
                            for identifier in sorted(previous_source_ids)
                        },
                        "evidence_record_registry": {
                            identifier: checkpoint["identity_state"][
                                "evidence_record_registry"
                            ][identifier]
                            for identifier in sorted(previous_evidence_ids)
                        },
                    }
                else:
                    registry_previous = None
                _validate_manifest_input_registry(
                    proposed_manifest,
                    registry_previous,
                    prepared["current_sources"],
                    prepared["current_evidence"],
                )

                event_semantics = {
                    item["event_id"]: item["semantic_hash"]
                    for item in loaded["events"]
                }
                has_new_event = False
                for event in prepared["proposed"]:
                    prior_semantic = event_semantics.get(event.event_id)
                    if prior_semantic is None:
                        has_new_event = True
                        event_semantics[event.event_id] = event.semantic_hash
                    elif prior_semantic != event.semantic_hash:
                        _fail(
                            "universe_event_id_conflict",
                            f"event_id {event.event_id!r} already has different semantics",
                        )
                if (
                    historical_identity["semantic_hash"]
                    != proposed_manifest["semantic_hash"]
                    or has_new_event
                ):
                    _fail(
                        "manifest_id_conflict",
                        f"manifest_id {proposed_manifest['manifest_id']!r} changed semantics",
                    )
                try:
                    _validate_manifest_clock_bindings(
                        proposed_manifest,
                        run_clock=prepared["verified_run"],
                        effective_clock=prepared["verified_effective"],
                    )
                except V2UniverseLedgerError as exc:
                    raise V2UniverseSegmentError(exc.code, exc.detail) from exc
                plan = {
                    "status": "duplicate",
                    "manifest": {
                        "manifest_id": historical_identity["manifest_id"],
                        "manifest_hash": historical_identity["manifest_hash"],
                    },
                }
            else:
                historical_batch_ids = {
                    item["event_batch_id"] for item in historical
                }
                plan = _classify_v2_universe_batch_append(
                    loaded,
                    prepared,
                    additional_committed_event_batch_ids=historical_batch_ids,
                )
        else:
            plan = _classify_v2_universe_batch_append(loaded, prepared)
        if plan["status"] == "duplicate":
            _assert_head_identity(head_path, old_head_bytes)
            return {
                "status": "duplicate",
                "rows_written": 0,
                "event_rows_written": 0,
                "segment_reused": False,
                "segment_hash": None,
                "head_hash": old_head["head_hash"],
                "manifest_id": plan["manifest"]["manifest_id"],
                "manifest_hash": plan["manifest"]["manifest_hash"],
                "event_count": old_head["event_count"],
                "manifest_count": old_head["manifest_count"],
                "path": str(head_path),
            }

        segment = validate_segmented_segment(
            _build_segment(
                checkpoint_hash=checkpoint["checkpoint_hash"],
                sequence=(
                    old_head["manifest_count"] - checkpoint["manifest_count"] + 1
                ),
                previous_segment_hash=old_head["tail_segment_hash"],
                events=plan["new_events"],
                manifest=plan["manifest"],
                before_event_count=old_head["event_count"],
                before_manifest_count=old_head["manifest_count"],
            )
        )
        segment_path = segmented_record_path(
            root_path, "segment", segment["segment_hash"]
        )
        segment_reused = _publish_immutable_record(
            segment_path, segment, role="segment"
        )
        if validate_segmented_segment(
            _read_json(segment_path, role="segment")
        ) != segment:
            _fail(
                "segmented_segment_publish_mismatch",
                "published segment differs from the planned record",
            )
        new_head = validate_segmented_head(_build_head(checkpoint, [segment]))
        _atomic_publish_head(
            head_path,
            new_head,
            expected_bytes=old_head_bytes,
        )
        committed, _, _ = _load_hot_store(root_path, "HEAD.json")
        expected_view = {
            "events": plan["events"],
            "manifests": plan["manifests"],
        }
        if committed != expected_view:
            _fail(
                "segmented_publish_verification_failed",
                "published segment does not reconstruct the planned ledger",
            )
        return {
            "status": "appended",
            "rows_written": len(plan["new_events"]) + 1,
            "event_rows_written": len(plan["new_events"]),
            "segment_reused": segment_reused,
            "segment_hash": segment["segment_hash"],
            "head_hash": new_head["head_hash"],
            "manifest_id": plan["manifest"]["manifest_id"],
            "manifest_hash": plan["manifest"]["manifest_hash"],
            "event_count": new_head["event_count"],
            "manifest_count": new_head["manifest_count"],
            "path": str(head_path),
        }


def rotate_segmented_v2_universe_checkpoint(
    root: str | Path,
    *,
    lock_timeout_seconds: float = _LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Atomically replace one validated generation with a compact hot checkpoint."""

    timeout = _validated_lock_timeout(lock_timeout_seconds)
    root_path = Path(root)
    head_path = root_path / "HEAD.json"
    lock_path = root_path / "HEAD.json.lock"
    _validate_segmented_lock_path(lock_path)
    with _exclusive_ledger_lock(lock_path, timeout_seconds=timeout):
        old_head = validate_segmented_head(_read_json(head_path, role="head"))
        old_head_bytes = _canonical_record_bytes(old_head)
        _assert_head_identity(head_path, old_head_bytes)
        _, _, hot_metadata = _load_hot_store(root_path, "HEAD.json")
        _assert_head_identity(head_path, old_head_bytes)
        old_checkpoint = hot_metadata["checkpoint"]
        if hot_metadata["compact"] and old_head["tail_segment_hash"] is None:
            return {
                "status": "already_compact",
                "rows_written": 0,
                "checkpoint_reused": True,
                "new_checkpoint_hash": old_head["checkpoint_hash"],
                "old_checkpoint_hash": old_head["checkpoint_hash"],
                "head_hash": old_head["head_hash"],
                "event_count": old_head["event_count"],
                "manifest_count": old_head["manifest_count"],
                "path": str(head_path),
            }

        exact, _ = _load_reachable_store(root_path, "HEAD.json")
        _assert_head_identity(head_path, old_head_bytes)
        checkpoint = validate_segmented_compact_checkpoint(
            _build_compact_checkpoint(
                exact,
                compacted_from_head=old_head,
            )
        )
        checkpoint_path = segmented_record_path(
            root_path, "checkpoint", checkpoint["checkpoint_hash"]
        )
        checkpoint_reused = _publish_immutable_record(
            checkpoint_path, checkpoint, role="checkpoint"
        )
        if _validate_checkpoint_record(
            _read_json(checkpoint_path, role="checkpoint")
        ) != checkpoint:
            _fail(
                "segmented_checkpoint_publish_mismatch",
                "published compact checkpoint differs from the planned record",
            )
        new_head = validate_segmented_head(_build_head(checkpoint, []))
        for field in (
            "event_count",
            "manifest_count",
            "head_manifest_id",
            "head_manifest_hash",
            "universe_id",
            "universe_definition_id",
            "universe_definition_version",
            "universe_definition_sha256",
            *_BOUNDARY,
        ):
            if new_head[field] != old_head[field]:
                _fail(
                    "segmented_rotation_identity_mismatch",
                    f"rotation changed logical field {field}",
                )
        _atomic_publish_head(
            head_path,
            new_head,
            expected_bytes=old_head_bytes,
        )
        committed_hot, _, committed_metadata = _load_hot_store(
            root_path, "HEAD.json"
        )
        if (
            committed_hot["events"] != exact["events"]
            or committed_hot["manifests"] != [exact["manifests"][-1]]
            or committed_metadata["head"] != new_head
        ):
            _fail(
                "segmented_rotation_verification_failed",
                "compact hot state differs from the pre-rotation logical tip",
            )
        committed_exact = load_segmented_v2_universe_ledger(root_path)
        if committed_exact != exact:
            _fail(
                "segmented_rotation_verification_failed",
                "compact archival lineage does not preserve exact legacy history",
            )
        return {
            "status": "rotated",
            "rows_written": 1 if checkpoint_reused else 2,
            "checkpoint_reused": checkpoint_reused,
            "new_checkpoint_hash": checkpoint["checkpoint_hash"],
            "old_checkpoint_hash": old_checkpoint["checkpoint_hash"],
            "head_hash": new_head["head_hash"],
            "event_count": new_head["event_count"],
            "manifest_count": new_head["manifest_count"],
            "path": str(head_path),
        }


def audit_segmented_v2_universe_ledger_orphans(
    root: str | Path,
    *,
    head_path: str | Path = "HEAD.json",
    lock_timeout_seconds: float = _LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Classify hot, superseded, and orphan records without adopting any."""

    timeout = _validated_lock_timeout(lock_timeout_seconds)
    root_path = Path(root)
    root_lexical = Path(os.path.abspath(root_path))
    lock_path = root_path / "HEAD.json.lock"
    _validate_segmented_lock_path(lock_path)
    with _exclusive_ledger_lock(lock_path, timeout_seconds=timeout):
        _, hot_reachable, _ = _load_hot_store(root_path, head_path)
        _, all_reachable = _load_reachable_store(root_path, head_path)
        candidates: list[Path] = []
        invalid_entries: list[Path] = []
        for directory in (
            root_lexical / "checkpoints",
            root_lexical / "segments",
        ):
            if not os.path.lexists(directory):
                continue
            try:
                escaped = (
                    directory.resolve()
                    != root_path.resolve() / directory.name
                )
            except (OSError, RuntimeError):
                escaped = True
            if directory.is_symlink() or escaped or not directory.is_dir():
                invalid_entries.append(directory)
                continue
            candidates.extend(
                item
                for item in directory.glob("*.json")
                if item.is_symlink() or item.is_file()
            )
        invalid = sorted(
            item.relative_to(root_lexical).as_posix()
            for item in [
                *invalid_entries,
                *(item for item in candidates if item.is_symlink()),
            ]
        )
        regular = [item for item in candidates if not item.is_symlink()]
        orphans = sorted(
            item.relative_to(root_lexical).as_posix()
            for item in regular
            if item.resolve() not in all_reachable
        )
        superseded = sorted(
            item.relative_to(root_lexical).as_posix()
            for item in regular
            if item.resolve() in all_reachable
            and item.resolve() not in hot_reachable
        )
    return {
        "orphan_files": orphans,
        "orphan_count": len(orphans),
        "superseded_files": superseded,
        "superseded_count": len(superseded),
        "invalid_files": invalid,
        "invalid_count": len(invalid),
        "authority": "research_only",
        "trade_enabled": False,
    }


__all__ = [
    "SCHEMA_VERSION",
    "HEAD_RECORD_TYPE",
    "CHECKPOINT_RECORD_TYPE",
    "COMPACT_CHECKPOINT_RECORD_TYPE",
    "SEGMENT_RECORD_TYPE",
    "STORAGE_CONTRACT",
    "V2UniverseSegmentError",
    "build_segmented_ledger_contract",
    "validate_segmented_head",
    "validate_segmented_checkpoint",
    "validate_segmented_compact_checkpoint",
    "validate_segmented_segment",
    "segmented_record_path",
    "load_segmented_v2_universe_ledger",
    "load_segmented_v2_universe_state",
    "bootstrap_segmented_v2_universe_ledger",
    "append_segmented_v2_universe_batch",
    "rotate_segmented_v2_universe_checkpoint",
    "audit_segmented_v2_universe_ledger_orphans",
]
