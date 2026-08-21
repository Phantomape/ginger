"""Read-only runtime adapter for the V2 SEC 8-K universe surface.

The adapter verifies the immutable SEC materialization before exposing the
single shared daily/replay membership snapshot.  It is a parity consumer only:
it does not create candidates, measure returns, or grant paper/live eligibility.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .v2_contracts import canonical_hash
from .v2_sec_8k_universe import (
    UNIVERSE_ID,
    V2SEC8KUniverseError,
    validate_persisted_sec_8k_materialization,
)
from .v2_universe_ledger import read_v2_daily_universe, read_v2_replay_universe


SCHEMA_VERSION = 1
ADAPTER_RECORD_TYPE = "v2_sec_8k_runtime_universe_snapshot"
ADAPTER_CONTRACT = "v2_sec_8k_runtime_universe_adapter_v1"


class V2SEC8KRuntimeAdapterError(RuntimeError):
    """SEC 8-K runtime adapter failed with a stable machine code."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.detail = str(message)
        super().__init__(f"[{self.code}] {self.detail}")


def _fail(code: str, message: str) -> None:
    raise V2SEC8KRuntimeAdapterError(code, message)


def _read_json(path: str | Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V2SEC8KRuntimeAdapterError(
            "runtime_materialization_unreadable", f"cannot read {path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        _fail("runtime_materialization_invalid", "materialization must be a JSON object")
    return raw


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


def read_sec_8k_runtime_universe(
    source_dir: str | Path,
    ledger_path: str | Path,
    envelope_path: str | Path,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Expose the SEC 8-K materialized universe through one daily/replay reader.

    ``as_of`` defaults to the immutable manifest's ``membership_as_of``.  The
    returned adapter snapshot includes only identity, membership, and parity
    metadata; no outcomes or ranking fields are read or produced.
    """

    try:
        verified = validate_persisted_sec_8k_materialization(
            source_dir, ledger_path, envelope_path
        )
    except V2SEC8KUniverseError as exc:
        raise V2SEC8KRuntimeAdapterError(exc.code, exc.detail) from exc
    envelope = _read_json(envelope_path)
    boundary = _require_research_only_boundary(envelope)
    manifest = envelope.get("universe_manifest")
    coverage = envelope.get("coverage_snapshot")
    if not isinstance(manifest, Mapping) or not isinstance(coverage, Mapping):
        _fail("runtime_materialization_invalid", "manifest and coverage are required")
    if verified["manifest_hash"] != manifest.get("manifest_hash"):
        _fail("runtime_manifest_hash_mismatch", "verified manifest hash changed")
    if verified["coverage_snapshot_hash"] != coverage.get("record_hash"):
        _fail("runtime_coverage_hash_mismatch", "verified coverage hash changed")
    resolved_as_of = as_of or str(manifest["membership_as_of"])

    daily = read_v2_daily_universe(
        ledger_path,
        manifest_id=str(manifest["manifest_id"]),
        as_of=resolved_as_of,
        universe_id=UNIVERSE_ID,
    )
    replay = read_v2_replay_universe(
        ledger_path,
        manifest_id=str(manifest["manifest_id"]),
        as_of=resolved_as_of,
        universe_id=UNIVERSE_ID,
    )
    if daily != replay:
        _fail("runtime_daily_replay_drift", "daily and replay readers diverged")
    if daily["manifest_hash"] != manifest["manifest_hash"]:
        _fail("runtime_manifest_hash_mismatch", "reader returned a different manifest")
    if daily["trade_enabled"] is not False or daily["paper_live_eligible"] is not False:
        _fail("runtime_boundary_escalation_forbidden", "reader boundary escalated")

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "record_type": ADAPTER_RECORD_TYPE,
        "adapter_contract": ADAPTER_CONTRACT,
        "source_frame": "sec_edgar_8k",
        "source_bundle_id": envelope["input_bundle_id"],
        "source_bundle_sha256": envelope["input_bundle_sha256"],
        "envelope_hash": envelope["envelope_hash"],
        "coverage_snapshot_id": coverage["coverage_snapshot_id"],
        "coverage_snapshot_hash": coverage["record_hash"],
        "manifest_id": manifest["manifest_id"],
        "manifest_hash": manifest["manifest_hash"],
        "as_of": daily["as_of"],
        "reader_contract": daily["reader_contract"],
        "membership_count": len(daily["memberships"]),
        "membership_snapshot_sha256": daily["membership_snapshot_sha256"],
        "daily_snapshot_hash": daily["snapshot_hash"],
        "replay_snapshot_hash": replay["snapshot_hash"],
        "daily_replay_identical": True,
        "membership_snapshot": deepcopy(daily),
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
    "V2SEC8KRuntimeAdapterError",
    "read_sec_8k_runtime_universe",
    "read_sec_8k_daily_runtime_universe",
    "read_sec_8k_replay_runtime_universe",
]
