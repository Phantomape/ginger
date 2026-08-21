"""Read-only checkpoint/segment sidecar contract for the V2 universe ledger.

The existing mixed JSONL ledger remains the logical truth and is not modified by
this module.  A constant-size ``HEAD.json`` selects one immutable checkpoint and
an optional hash-linked tail of one-transaction segments.  Loading reconstructs
the exact legacy ``events``/``manifests`` view and delegates final validation to
the existing strict ledger parser.

This is deliberately a contract-only storage slice.  It does not publish files,
change the legacy writer or reader, establish an external append anchor, or
upgrade any research/PIT/trading boundary.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from .v2_contracts import (
    V2ContractValidationError,
    canonical_hash,
    canonical_json,
    validate_universe_event,
)
from .v2_universe_ledger import (
    V2UniverseLedgerError,
    _instant,
    _load_ledger_text,
    _membership_semantic_rows,
    _validate_manifest_shape,
    validate_universe_event_population,
)


SCHEMA_VERSION = 1
HEAD_RECORD_TYPE = "v2_universe_segmented_head"
CHECKPOINT_RECORD_TYPE = "v2_universe_ledger_checkpoint"
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
        segments[-1]["manifest"] if segments else checkpoint["manifests"][-1]
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


def segmented_record_path(root: str | Path, kind: str, record_hash: str) -> Path:
    digest = _require_hash(record_hash, field=f"{kind}_hash")
    if kind == "checkpoint":
        return Path(root) / "checkpoints" / f"{digest}.json"
    if kind == "segment":
        return Path(root) / "segments" / f"{digest}.json"
    _fail("segmented_record_kind_invalid", "kind must be checkpoint or segment")


def _read_json(path: Path, *, role: str) -> dict[str, Any]:
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


def _load_reachable_store(
    root: Path, head_path: str | Path
) -> tuple[dict[str, list[dict[str, Any]]], set[Path]]:
    head_target = Path(head_path)
    if not head_target.is_absolute():
        head_target = root / head_target
    head = validate_segmented_head(_read_json(head_target, role="head"))
    checkpoint_path = segmented_record_path(root, "checkpoint", head["checkpoint_hash"])
    checkpoint = validate_segmented_checkpoint(
        _read_json(checkpoint_path, role="checkpoint")
    )
    if checkpoint["checkpoint_hash"] != head["checkpoint_hash"]:
        _fail("segmented_checkpoint_binding_mismatch", "HEAD binds another checkpoint")

    checkpoint_view = {
        "events": deepcopy(checkpoint["events"]),
        "manifests": deepcopy(checkpoint["manifests"]),
    }

    reachable = {head_target.resolve(), checkpoint_path.resolve()}
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

    events = [deepcopy(item) for item in checkpoint_view["events"]]
    manifests = [deepcopy(item) for item in checkpoint_view["manifests"]]
    previous_hash = None
    for sequence, segment in enumerate(segments, start=1):
        previous_manifest = manifests[-1]
        if (
            segment["sequence"] != sequence
            or segment["previous_segment_hash"] != previous_hash
            or segment["before_event_count"] != len(events)
            or segment["before_manifest_count"] != len(manifests)
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
            before_manifest_count=len(manifests),
        )
        if segment != expected:
            _fail(
                "segmented_segment_state_mismatch",
                "segment metadata does not match its transaction",
            )
        events.extend(deepcopy(segment["events"]))
        manifests.append(deepcopy(segment["manifest"]))
        previous_hash = segment["segment_hash"]

    reconstructed = _canonical_legacy_view({"events": events, "manifests": manifests})
    final_manifest = reconstructed["manifests"][-1]
    if (
        head["tail_segment_hash"] != previous_hash
        or head["event_count"] != len(reconstructed["events"])
        or head["manifest_count"] != len(reconstructed["manifests"])
        or head["head_manifest_id"] != final_manifest["manifest_id"]
        or head["head_manifest_hash"] != final_manifest["manifest_hash"]
        or head["universe_id"] != final_manifest["universe_id"]
        or head["universe_definition_id"] != final_manifest["universe_definition_id"]
        or head["universe_definition_version"] != final_manifest["universe_definition_version"]
        or head["universe_definition_sha256"] != final_manifest["universe_definition_sha256"]
    ):
        _fail("segmented_head_state_mismatch", "HEAD does not bind the reconstructed ledger tip")
    return reconstructed, reachable


def load_segmented_v2_universe_ledger(
    root: str | Path, *, head_path: str | Path = "HEAD.json"
) -> dict[str, list[dict[str, Any]]]:
    """Load only the chain selected by HEAD and return the exact legacy view."""

    loaded, _ = _load_reachable_store(Path(root), head_path)
    return loaded


def audit_segmented_v2_universe_ledger_orphans(
    root: str | Path, *, head_path: str | Path = "HEAD.json"
) -> dict[str, Any]:
    """Report unreferenced content-addressed records without adopting them."""

    root_path = Path(root)
    _, reachable = _load_reachable_store(root_path, head_path)
    candidates = []
    for directory in (root_path / "checkpoints", root_path / "segments"):
        if directory.is_dir():
            candidates.extend(item.resolve() for item in directory.glob("*.json") if item.is_file())
    orphans = sorted(
        item.relative_to(root_path.resolve()).as_posix()
        for item in candidates
        if item not in reachable
    )
    return {
        "orphan_files": orphans,
        "orphan_count": len(orphans),
        "authority": "research_only",
        "trade_enabled": False,
    }


__all__ = [
    "SCHEMA_VERSION",
    "HEAD_RECORD_TYPE",
    "CHECKPOINT_RECORD_TYPE",
    "SEGMENT_RECORD_TYPE",
    "STORAGE_CONTRACT",
    "V2UniverseSegmentError",
    "build_segmented_ledger_contract",
    "validate_segmented_head",
    "validate_segmented_checkpoint",
    "validate_segmented_segment",
    "segmented_record_path",
    "load_segmented_v2_universe_ledger",
    "audit_segmented_v2_universe_ledger_orphans",
]
