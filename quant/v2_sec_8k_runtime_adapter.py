"""Read-only runtime adapter for the V2 SEC 8-K universe surface.

The adapter verifies the immutable SEC materialization before exposing the
single shared daily/replay membership snapshot.  It is a parity consumer only:
it does not create candidates, measure returns, or grant paper/live eligibility.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
import re
from typing import Any, Mapping

from .v2_contracts import canonical_hash
from .v2_sec_8k_universe import (
    UNIVERSE_ID,
    V2SEC8KUniverseError,
    validate_persisted_sec_8k_materialization,
    validate_persisted_sec_8k_materialization_against_state,
)
from .v2_universe_ledger import (
    V2UniverseLedgerError,
    _read_v2_universe_membership_from_validated_state,
    read_v2_universe_membership,
)
from .v2_universe_ledger_segments import (
    COMPACT_HEAD_STORAGE_CONTRACT,
    STORAGE_CONTRACT,
    load_segmented_v2_universe_state,
)


SCHEMA_VERSION = 3
ADAPTER_RECORD_TYPE = "v2_sec_8k_runtime_universe_snapshot"
ADAPTER_CONTRACT = "v2_sec_8k_runtime_universe_adapter_v3"
LEDGER_BACKEND_LEGACY_JSONL_V1 = "legacy_jsonl_v1"
LEDGER_BACKEND_SEGMENTED_HOT_V1 = "segmented_hot_v1"
_SUPPORTED_LEDGER_BACKENDS = {
    LEDGER_BACKEND_LEGACY_JSONL_V1,
    LEDGER_BACKEND_SEGMENTED_HOT_V1,
}


class V2SEC8KRuntimeAdapterError(RuntimeError):
    """SEC 8-K runtime adapter failed with a stable machine code."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.detail = str(message)
        super().__init__(f"[{self.code}] {self.detail}")


def _fail(code: str, message: str) -> None:
    raise V2SEC8KRuntimeAdapterError(code, message)


def _reject_nonfinite_json(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r} is forbidden")


def _parse_finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number {value!r} is forbidden")
    return parsed


def _read_json(path: str | Path) -> dict[str, Any]:
    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            parse_constant=_reject_nonfinite_json,
            parse_float=_parse_finite_json_float,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise V2SEC8KRuntimeAdapterError(
            "runtime_materialization_unreadable", f"cannot read {path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        _fail("runtime_materialization_invalid", "materialization must be a JSON object")
    payload = deepcopy(raw)
    supplied_hash = payload.pop("envelope_hash", None)
    if supplied_hash != canonical_hash(payload):
        _fail(
            "runtime_materialization_hash_mismatch",
            "materialization envelope hash is invalid",
        )
    return raw


def _required_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        _fail(f"runtime_{field}_invalid", f"{field} must be a non-empty trimmed string")
    return value


def _require_research_only_boundary(envelope: Mapping[str, Any]) -> dict[str, Any]:
    boundary = envelope.get("boundary")
    if not isinstance(boundary, Mapping):
        _fail("runtime_boundary_missing", "materialization boundary is missing")
    expected = {
        "external_universe_coverage_status": "unverified",
        "pit_tier": "research_pit",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "parity_status": "contract_only_unwired",
        "authority": "research_only",
        "trade_enabled": False,
    }
    observed = {key: boundary.get(key) for key in expected}
    if observed != expected:
        _fail("runtime_boundary_escalation_forbidden", "SEC 8-K runtime boundary changed")
    return dict(observed)


def _segmented_hot_state_identity(state: Mapping[str, Any]) -> dict[str, Any]:
    storage_contract = state.get("storage_contract")
    checkpoint_hash = state.get("checkpoint_hash")
    tail_segment_hash = state.get("tail_segment_hash")
    event_count = state.get("event_count")
    manifest_count = state.get("manifest_count")
    current_generation_manifest_count = state.get("current_generation_manifest_count")
    head_manifest = state.get("head_manifest")
    if (
        storage_contract not in {STORAGE_CONTRACT, COMPACT_HEAD_STORAGE_CONTRACT}
        or not isinstance(checkpoint_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", checkpoint_hash) is None
        or (
            tail_segment_hash is not None
            and (
                not isinstance(tail_segment_hash, str)
                or re.fullmatch(r"[0-9a-f]{64}", tail_segment_hash) is None
            )
        )
        or not isinstance(event_count, int)
        or isinstance(event_count, bool)
        or event_count < 0
        or not isinstance(manifest_count, int)
        or isinstance(manifest_count, bool)
        or manifest_count < 1
        or not isinstance(current_generation_manifest_count, int)
        or isinstance(current_generation_manifest_count, bool)
        or not 1 <= current_generation_manifest_count <= manifest_count
        or not isinstance(head_manifest, Mapping)
        or state.get("legacy_full_reader_compatible")
        != (storage_contract == STORAGE_CONTRACT)
        or state.get("authority") != "research_only"
        or state.get("trade_enabled") is not False
    ):
        _fail(
            "runtime_segmented_hot_state_invalid",
            "segmented hot state identity is malformed or crossed its boundary",
        )
    head_manifest_id = _required_text(
        head_manifest.get("manifest_id"), field="head_manifest_id"
    )
    head_manifest_hash = head_manifest.get("manifest_hash")
    if (
        not isinstance(head_manifest_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", head_manifest_hash) is None
    ):
        _fail(
            "runtime_segmented_hot_state_invalid",
            "segmented hot state head manifest hash is invalid",
        )
    return {
        "storage_contract": storage_contract,
        "checkpoint_hash": checkpoint_hash,
        "tail_segment_hash": tail_segment_hash,
        "event_count": event_count,
        "manifest_count": manifest_count,
        "current_generation_manifest_count": current_generation_manifest_count,
        "legacy_full_reader_compatible": state["legacy_full_reader_compatible"],
        "head_manifest_id": head_manifest_id,
        "head_manifest_hash": head_manifest_hash,
    }


def read_sec_8k_runtime_universe(
    source_dir: str | Path,
    envelope_path: str | Path,
    *,
    backend: str,
    storage_location: str | Path,
    manifest_id: str,
    as_of: str,
) -> dict[str, Any]:
    """Expose the SEC 8-K materialized universe through one daily/replay reader.

    The backend, storage location, and both identity inputs are mandatory.  The
    location is a JSONL file for legacy and a root directory for segmented-hot.
    The returned snapshot contains no outcomes or ranking fields.
    """

    selected_backend = _required_text(backend, field="ledger_backend")
    if selected_backend not in _SUPPORTED_LEDGER_BACKENDS:
        _fail(
            "runtime_ledger_backend_unsupported",
            "ledger_backend must select one supported reader explicitly",
        )
    requested_manifest_id = _required_text(manifest_id, field="manifest_id")
    requested_as_of = _required_text(as_of, field="as_of")
    envelope = _read_json(envelope_path)
    state = None
    segmented_hot_state_identity = None
    if selected_backend == LEDGER_BACKEND_LEGACY_JSONL_V1:
        try:
            verified = validate_persisted_sec_8k_materialization(
                source_dir, storage_location, envelope_path
            )
        except V2SEC8KUniverseError as exc:
            raise V2SEC8KRuntimeAdapterError(exc.code, exc.detail) from exc
    else:
        try:
            state = load_segmented_v2_universe_state(storage_location)
            verified = validate_persisted_sec_8k_materialization_against_state(
                source_dir, state, envelope_path
            )
            segmented_hot_state_identity = _segmented_hot_state_identity(state)
        except (V2SEC8KUniverseError, V2UniverseLedgerError) as exc:
            raise V2SEC8KRuntimeAdapterError(exc.code, exc.detail) from exc
    if verified["envelope_hash"] != envelope["envelope_hash"]:
        _fail(
            "runtime_envelope_identity_changed",
            "materialization changed between the adapter read and graph validation",
        )
    boundary = _require_research_only_boundary(envelope)
    manifest = envelope.get("universe_manifest")
    coverage = envelope.get("coverage_snapshot")
    if not isinstance(manifest, Mapping) or not isinstance(coverage, Mapping):
        _fail("runtime_materialization_invalid", "manifest and coverage are required")
    if (
        requested_manifest_id != verified["manifest_id"]
        or requested_manifest_id != manifest.get("manifest_id")
    ):
        _fail(
            "runtime_manifest_id_mismatch",
            "requested manifest_id does not match the validated materialization",
        )
    if verified["manifest_hash"] != manifest.get("manifest_hash"):
        _fail("runtime_manifest_hash_mismatch", "verified manifest hash changed")
    if verified["coverage_snapshot_hash"] != coverage.get("record_hash"):
        _fail("runtime_coverage_hash_mismatch", "verified coverage hash changed")

    try:
        if selected_backend == LEDGER_BACKEND_LEGACY_JSONL_V1:
            membership = read_v2_universe_membership(
                storage_location,
                manifest_id=requested_manifest_id,
                as_of=requested_as_of,
                universe_id=UNIVERSE_ID,
            )
        else:
            membership = _read_v2_universe_membership_from_validated_state(
                state,
                manifest_id=requested_manifest_id,
                as_of=requested_as_of,
                universe_id=UNIVERSE_ID,
            )
    except V2UniverseLedgerError as exc:
        raise V2SEC8KRuntimeAdapterError(exc.code, exc.detail) from exc
    if membership["manifest_hash"] != manifest["manifest_hash"]:
        _fail("runtime_manifest_hash_mismatch", "reader returned a different manifest")
    if (
        membership["trade_enabled"] is not False
        or membership["paper_live_eligible"] is not False
    ):
        _fail("runtime_boundary_escalation_forbidden", "reader boundary escalated")

    input_identity = {
        "source_bundle_id": envelope["input_bundle_id"],
        "source_bundle_sha256": envelope["input_bundle_sha256"],
        "envelope_hash": envelope["envelope_hash"],
        "coverage_snapshot_id": coverage["coverage_snapshot_id"],
        "coverage_snapshot_hash": coverage["record_hash"],
        "manifest_id": manifest["manifest_id"],
        "manifest_hash": manifest["manifest_hash"],
        "universe_id": membership["universe_id"],
        "universe_definition_id": membership["universe_definition_id"],
        "universe_definition_version": membership["universe_definition_version"],
        "universe_definition_sha256": membership["universe_definition_sha256"],
        "as_of": membership["as_of"],
        "reader_contract": membership["reader_contract"],
        "ledger_backend": selected_backend,
        "segmented_hot_state_identity_sha256": (
            None
            if segmented_hot_state_identity is None
            else canonical_hash(segmented_hot_state_identity)
        ),
    }
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "record_type": ADAPTER_RECORD_TYPE,
        "adapter_contract": ADAPTER_CONTRACT,
        "source_frame": "sec_edgar_8k",
        "ledger_backend": selected_backend,
        "segmented_hot_state_identity": segmented_hot_state_identity,
        "input_identity": input_identity,
        "input_identity_sha256": canonical_hash(input_identity),
        "membership_count": len(membership["memberships"]),
        "membership_snapshot_sha256": membership["membership_snapshot_sha256"],
        "shared_reader_snapshot_hash": membership["snapshot_hash"],
        "adapter_parity_status": "daily_replay_verified_research_only",
        "adapter_parity_scope": (
            "explicit_backend_exact_source_graph_manifest_as_of_membership"
        ),
        "membership_snapshot": deepcopy(membership),
        "boundary": boundary,
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    snapshot["adapter_snapshot_hash"] = canonical_hash(snapshot)
    return snapshot


# These are true aliases so consumer labels cannot fork runtime membership logic.
read_sec_8k_daily_runtime_universe = read_sec_8k_runtime_universe
read_sec_8k_replay_runtime_universe = read_sec_8k_runtime_universe


__all__ = [
    "ADAPTER_CONTRACT",
    "ADAPTER_RECORD_TYPE",
    "SCHEMA_VERSION",
    "LEDGER_BACKEND_LEGACY_JSONL_V1",
    "LEDGER_BACKEND_SEGMENTED_HOT_V1",
    "V2SEC8KRuntimeAdapterError",
    "read_sec_8k_runtime_universe",
    "read_sec_8k_daily_runtime_universe",
    "read_sec_8k_replay_runtime_universe",
]
