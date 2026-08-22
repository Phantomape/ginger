"""Default-off pre-Engine-0 observation boundary for V2 universe inputs.

This module consumes a validated runtime adapter snapshot in memory and exposes
only the exact universe membership surface that a future Engine-0 policy may
inspect after separate eligibility and market-clock gates.  It does not create
candidates, scores, decisions, outcomes, or orders.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Mapping

from .v2_contracts import canonical_hash
from .v2_sec_8k_runtime_adapter import (
    ADAPTER_CONTRACT,
    ADAPTER_RECORD_TYPE,
    LEDGER_BACKEND_LEGACY_JSONL_V1,
    LEDGER_BACKEND_SEGMENTED_HOT_V1,
    read_sec_8k_runtime_universe,
)


SCHEMA_VERSION = 2
OBSERVATION_RECORD_TYPE = "v2_pre_engine0_universe_observation_snapshot"
OBSERVATION_CONTRACT = "v2_pre_engine0_default_off_universe_observation_v2"

_RESEARCH_ONLY_BOUNDARY = {
    "external_universe_coverage_status": "unverified",
    "pit_tier": "research_pit",
    "result_ceiling": "observed_only",
    "paper_live_eligible": False,
    "parity_status": "contract_only_unwired",
    "authority": "research_only",
    "trade_enabled": False,
}
_MEMBERSHIP_FIELDS = (
    "mapping_id",
    "security_id",
    "listing_id",
    "symbol",
    "mic",
    "mapping_sha256",
    "state",
    "latest_event_id",
    "latest_event_semantic_hash",
    "latest_event_hash",
    "effective_at",
)
_MEMBERSHIP_HASH_FIELDS = {
    "mapping_sha256",
    "latest_event_semantic_hash",
    "latest_event_hash",
}
_UNIVERSE_STATES = {
    "discovered",
    "research_eligible",
    "candidate_eligible",
    "quarantine",
    "retired",
}


class V2UniverseObservationError(RuntimeError):
    """Pre-Engine-0 observation input failed with a stable machine code."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.detail = str(message)
        super().__init__(f"[{self.code}] {self.detail}")


def _fail(code: str, message: str) -> None:
    raise V2UniverseObservationError(code, message)


def _mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("observation_runtime_invalid", f"{field} must be an object")
    return value


def _validated_runtime_snapshot(
    runtime: Mapping[str, Any],
) -> tuple[Mapping[str, Any], list[dict[str, str]]]:
    if (
        runtime.get("record_type") != ADAPTER_RECORD_TYPE
        or runtime.get("adapter_contract") != ADAPTER_CONTRACT
        or runtime.get("source_frame") != "sec_edgar_8k"
        or runtime.get("adapter_parity_status")
        != "daily_replay_verified_research_only"
    ):
        _fail("observation_runtime_contract_mismatch", "unexpected runtime adapter contract")

    runtime_payload = deepcopy(dict(runtime))
    supplied_runtime_hash = runtime_payload.pop("adapter_snapshot_hash", None)
    if supplied_runtime_hash != canonical_hash(runtime_payload):
        _fail("observation_runtime_hash_mismatch", "runtime adapter hash is invalid")

    runtime_identity = _mapping(
        runtime.get("input_identity"), field="runtime.input_identity"
    )
    if runtime.get("input_identity_sha256") != canonical_hash(runtime_identity):
        _fail(
            "observation_runtime_identity_hash_mismatch",
            "runtime input identity hash is invalid",
        )
    ledger_backend = runtime.get("ledger_backend")
    hot_state_identity = runtime.get("segmented_hot_state_identity")
    hot_state_identity_sha256 = runtime_identity.get(
        "segmented_hot_state_identity_sha256"
    )
    if (
        "ledger_backend" not in runtime
        or "segmented_hot_state_identity" not in runtime
        or "ledger_backend" not in runtime_identity
        or "segmented_hot_state_identity_sha256" not in runtime_identity
        or not isinstance(ledger_backend, str)
        or ledger_backend not in {
            LEDGER_BACKEND_LEGACY_JSONL_V1,
            LEDGER_BACKEND_SEGMENTED_HOT_V1,
        }
        or runtime_identity.get("ledger_backend") != ledger_backend
        or (
            ledger_backend == LEDGER_BACKEND_LEGACY_JSONL_V1
            and (hot_state_identity is not None or hot_state_identity_sha256 is not None)
        )
        or (
            ledger_backend == LEDGER_BACKEND_SEGMENTED_HOT_V1
            and (
                not isinstance(hot_state_identity, Mapping)
                or hot_state_identity_sha256 != canonical_hash(hot_state_identity)
            )
        )
    ):
        _fail(
            "observation_runtime_backend_identity_mismatch",
            "runtime backend identity is missing or contradictory",
        )

    boundary = _mapping(runtime.get("boundary"), field="runtime.boundary")
    observed_boundary = {
        key: boundary.get(key) for key in _RESEARCH_ONLY_BOUNDARY
    }
    if observed_boundary != _RESEARCH_ONLY_BOUNDARY:
        _fail("observation_boundary_escalation_forbidden", "runtime boundary changed")
    if (
        runtime.get("outcome_blind") is not True
        or runtime.get("results_accessed") is not False
        or runtime.get("authority") != "research_only"
        or runtime.get("trade_enabled") is not False
    ):
        _fail("observation_boundary_escalation_forbidden", "runtime authority changed")

    membership = _mapping(
        runtime.get("membership_snapshot"), field="runtime.membership_snapshot"
    )
    membership_payload = deepcopy(dict(membership))
    supplied_membership_hash = membership_payload.pop("snapshot_hash", None)
    if supplied_membership_hash != canonical_hash(membership_payload):
        _fail("observation_membership_hash_mismatch", "membership snapshot hash is invalid")
    memberships = membership.get("memberships")
    if not isinstance(memberships, list):
        _fail("observation_runtime_invalid", "membership rows must be a list")
    observed_memberships: list[dict[str, str]] = []
    for index, row in enumerate(memberships):
        if not isinstance(row, Mapping) or set(row) != set(_MEMBERSHIP_FIELDS):
            _fail(
                "observation_membership_shape_invalid",
                f"memberships[{index}] has an unexpected field surface",
            )
        projected: dict[str, str] = {}
        for field in _MEMBERSHIP_FIELDS:
            value = row.get(field)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                _fail(
                    "observation_membership_shape_invalid",
                    f"memberships[{index}].{field} must be non-empty text",
                )
            if field in _MEMBERSHIP_HASH_FIELDS and re.fullmatch(
                r"[0-9a-f]{64}", value
            ) is None:
                _fail(
                    "observation_membership_shape_invalid",
                    f"memberships[{index}].{field} must be a lowercase SHA-256",
                )
            if field == "state" and value not in _UNIVERSE_STATES:
                _fail(
                    "observation_membership_shape_invalid",
                    f"memberships[{index}].state is unsupported",
                )
            if field == "effective_at":
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    parsed = None
                if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
                    _fail(
                        "observation_membership_shape_invalid",
                        f"memberships[{index}].effective_at must include a timezone",
                    )
                value = parsed.astimezone(timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                )
            projected[field] = value
        observed_memberships.append(projected)
    expected_order = sorted(
        observed_memberships,
        key=lambda row: (row["security_id"], row["listing_id"]),
    )
    if observed_memberships != expected_order:
        _fail(
            "observation_membership_order_invalid",
            "membership rows are not identity-sorted",
        )
    if (
        len({row["security_id"] for row in observed_memberships})
        != len(observed_memberships)
        or len({row["listing_id"] for row in observed_memberships})
        != len(observed_memberships)
    ):
        _fail(
            "observation_membership_identity_duplicate",
            "membership rows repeat a security or listing identity",
        )
    membership_count = runtime.get("membership_count")
    if (
        not isinstance(membership_count, int)
        or isinstance(membership_count, bool)
        or membership_count != len(memberships)
    ):
        _fail("observation_membership_count_mismatch", "membership count changed")
    if (
        runtime.get("membership_snapshot_sha256")
        != membership.get("membership_snapshot_sha256")
        or runtime.get("shared_reader_snapshot_hash") != supplied_membership_hash
    ):
        _fail("observation_membership_identity_mismatch", "membership identity changed")
    semantic_rows = [
        {
            key: value
            for key, value in row.items()
            if key != "latest_event_hash"
        }
        for row in observed_memberships
    ]
    if canonical_hash(semantic_rows) != membership.get("membership_snapshot_sha256"):
        _fail(
            "observation_membership_identity_mismatch",
            "membership semantic hash is invalid",
        )
    observed_membership_boundary = {
        key: membership.get(key) for key in _RESEARCH_ONLY_BOUNDARY
    }
    if observed_membership_boundary != _RESEARCH_ONLY_BOUNDARY:
        _fail(
            "observation_boundary_escalation_forbidden",
            "membership boundary changed",
        )
    if membership.get("outcome_blind") is not True or membership.get(
        "results_accessed"
    ) is not False:
        _fail(
            "observation_boundary_escalation_forbidden",
            "membership result boundary changed",
        )
    identity_fields = (
        "manifest_id",
        "manifest_hash",
        "universe_id",
        "universe_definition_id",
        "universe_definition_version",
        "universe_definition_sha256",
        "as_of",
        "reader_contract",
    )
    if any(
        runtime_identity.get(field) != membership.get(field)
        for field in identity_fields
    ):
        _fail(
            "observation_runtime_identity_mismatch",
            "runtime identity contradicts the membership snapshot",
        )
    if ledger_backend == LEDGER_BACKEND_SEGMENTED_HOT_V1 and (
        hot_state_identity.get("head_manifest_id") != membership.get("manifest_id")
        or hot_state_identity.get("head_manifest_hash")
        != membership.get("manifest_hash")
    ):
        _fail(
            "observation_runtime_backend_identity_mismatch",
            "segmented hot state does not bind the observed manifest tip",
        )
    return membership, observed_memberships


def observe_sec_8k_universe(
    source_dir: str | Path,
    envelope_path: str | Path,
    *,
    backend: str,
    storage_location: str | Path,
    manifest_id: str,
    as_of: str,
) -> dict[str, Any]:
    """Observe one explicit SEC 8-K universe snapshot without decision logic."""

    runtime = read_sec_8k_runtime_universe(
        source_dir,
        envelope_path,
        backend=backend,
        storage_location=storage_location,
        manifest_id=manifest_id,
        as_of=as_of,
    )
    membership, memberships = _validated_runtime_snapshot(runtime)
    input_identity = {
        "runtime_adapter_contract": runtime["adapter_contract"],
        "runtime_adapter_snapshot_hash": runtime["adapter_snapshot_hash"],
        "runtime_input_identity_sha256": runtime["input_identity_sha256"],
        "manifest_id": membership["manifest_id"],
        "manifest_hash": membership["manifest_hash"],
        "universe_id": membership["universe_id"],
        "universe_definition_id": membership["universe_definition_id"],
        "universe_definition_version": membership["universe_definition_version"],
        "universe_definition_sha256": membership["universe_definition_sha256"],
        "as_of": membership["as_of"],
        "membership_snapshot_sha256": membership["membership_snapshot_sha256"],
        "shared_reader_snapshot_hash": membership["snapshot_hash"],
        "ledger_backend": runtime["ledger_backend"],
        "segmented_hot_state_identity_sha256": runtime["input_identity"][
            "segmented_hot_state_identity_sha256"
        ],
    }
    observation = {
        "schema_version": SCHEMA_VERSION,
        "record_type": OBSERVATION_RECORD_TYPE,
        "observation_contract": OBSERVATION_CONTRACT,
        "consumer_stage": "pre_engine0_universe_observation",
        "source_frame": "sec_edgar_8k",
        "ledger_backend": runtime["ledger_backend"],
        "input_identity": input_identity,
        "input_identity_sha256": canonical_hash(input_identity),
        "membership_count": len(memberships),
        "memberships": memberships,
        "membership_snapshot_sha256": membership["membership_snapshot_sha256"],
        "observation_parity_status": "daily_replay_alias_verified_research_only",
        "observation_scope": "source_bound_universe_membership_only",
        "engine0_policy_invoked": False,
        "engine0_baseline_established": False,
        "market_decision_clock_status": "unwired",
        "boundary": deepcopy(_RESEARCH_ONLY_BOUNDARY),
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    observation["observation_snapshot_hash"] = canonical_hash(observation)
    return observation


# Daily and replay cannot fork the observation or membership logic.
observe_sec_8k_daily_universe = observe_sec_8k_universe
observe_sec_8k_replay_universe = observe_sec_8k_universe


__all__ = [
    "OBSERVATION_CONTRACT",
    "OBSERVATION_RECORD_TYPE",
    "SCHEMA_VERSION",
    "V2UniverseObservationError",
    "observe_sec_8k_universe",
    "observe_sec_8k_daily_universe",
    "observe_sec_8k_replay_universe",
]
