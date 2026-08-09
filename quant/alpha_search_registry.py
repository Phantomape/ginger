"""Strict registry for alpha-search evidence surfaces.

The registry validates every row through :class:`EvidenceSurface`; it does not
invent readiness from file existence, ledger row counts, or prose.  Two views
are exposed deliberately:

``source_contract``
    Stable source identity, component-source membership, role, artifact
    locators, expectation-proxy semantics, source-contract status, and the
    exact as-of/artifact-hash anchors used by the audited snapshot.

``readiness``
    The current PIT/evidence-grade/settlement/gate-ready snapshot.

Keeping their hashes separate shows whether counts/saturation changed without
a semantic source change.  The shared as-of/artifact anchors intentionally
change both hashes when the frozen source vintage changes.  Changing a join's
``component_sources`` changes the source-contract hash and cannot be hidden by
an unchanged primary ``data_source`` label.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Iterator, Mapping, Sequence

try:  # Support package imports and direct ``quant/`` script execution.
    from .alpha_search_contract import (
        EvidenceSurface,
        canonical_hash as _contract_canonical_hash,
        canonical_json as _contract_canonical_json,
        validate_evidence_surface,
    )
    from .data_paths import data_artifact_path
except ImportError:  # pragma: no cover - script-style import fallback.
    from alpha_search_contract import (  # type: ignore
        EvidenceSurface,
        canonical_hash as _contract_canonical_hash,
        canonical_json as _contract_canonical_json,
        validate_evidence_surface,
    )
    from data_paths import data_artifact_path


SCHEMA_VERSION = 1
DEFAULT_REGISTRY_PATH = data_artifact_path("alpha_search_evidence_surfaces")

_ROOT_FIELDS = frozenset({"schema_version", "surfaces"})
_SOURCE_CONTRACT_FIELDS = (
    "schema_version",
    "surface_id",
    "data_source",
    "component_sources",
    "roles",
    "artifacts",
    "expectation_proxy",
)
_READINESS_FIELDS = (
    "surface_id",
    "pit_status",
    "evidence_grade",
    "independent_count",
    "settled_count",
    "candidate_overlap_count",
    "gate_ready",
    "saturation_status",
    "reopen_condition",
    # Status and immutable artifact bindings describe the current snapshot,
    # not a new data-source identity.  A partial->pass refresh therefore
    # changes readiness without masquerading as a new source contract.
    "source_contract_status",
    "as_of",
    "artifact_snapshot_hashes",
)


class EvidenceSurfaceRegistryError(ValueError):
    """Base class for fail-closed registry errors."""


class EvidenceSurfaceRegistryValidationError(EvidenceSurfaceRegistryError):
    """The registry document or one of its surfaces is invalid."""


class UnknownEvidenceSurfaceError(EvidenceSurfaceRegistryError, KeyError):
    """A candidate refers to a surface that is absent from the registry."""


def _validate_json_value(value: Any, *, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvidenceSurfaceRegistryValidationError(f"{path} must be finite")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise EvidenceSurfaceRegistryValidationError(
                    f"{path} keys must be strings"
                )
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise EvidenceSurfaceRegistryValidationError(
        f"{path} contains non-JSON value {type(value).__name__}"
    )


def _canonical_json(value: Any) -> str:
    _validate_json_value(value, path="value")
    try:
        return _contract_canonical_json(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive.
        raise EvidenceSurfaceRegistryValidationError(
            f"value is not canonical JSON: {exc}"
        ) from exc


def canonical_hash(value: Any) -> str:
    """Return a full SHA-256 digest over canonical JSON."""
    _validate_json_value(value, path="value")
    return _contract_canonical_hash(value)


def _surface_dict(surface: EvidenceSurface) -> dict[str, Any]:
    value = surface.to_dict()
    if not isinstance(value, Mapping):  # pragma: no cover - contract defence.
        raise EvidenceSurfaceRegistryValidationError(
            "EvidenceSurface.to_dict() must return an object"
        )
    # Round-trip to detach nested structures from a caller-owned object.
    return json.loads(_canonical_json(dict(value)))


def _normalise_surface(
    value: EvidenceSurface | Mapping[str, Any], *, index: int
) -> EvidenceSurface:
    try:
        return validate_evidence_surface(value)
    except Exception as exc:
        # ContractValidationError is intentionally not coupled here; callers
        # get a registry-local, path-qualified failure regardless of its exact
        # implementation details.
        raise EvidenceSurfaceRegistryValidationError(
            f"surfaces[{index}] is invalid: {exc}"
        ) from exc


class EvidenceSurfaceRegistry:
    """Immutable, validated collection of evidence-surface contracts."""

    def __init__(
        self,
        surfaces: Iterable[EvidenceSurface | Mapping[str, Any]],
    ) -> None:
        normalised: list[EvidenceSurface] = []
        by_id: dict[str, EvidenceSurface] = {}
        for index, value in enumerate(surfaces):
            surface = _normalise_surface(value, index=index)
            surface_id = str(surface.surface_id)
            if surface_id in by_id:
                raise EvidenceSurfaceRegistryValidationError(
                    f"duplicate surface_id {surface_id!r}"
                )
            by_id[surface_id] = surface
            normalised.append(surface)

        normalised.sort(key=lambda item: str(item.surface_id))
        self._surfaces = tuple(normalised)
        self._by_id = MappingProxyType(
            {str(surface.surface_id): surface for surface in self._surfaces}
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvidenceSurfaceRegistry":
        """Build a registry from its strict versioned JSON representation."""

        if not isinstance(payload, Mapping):
            raise EvidenceSurfaceRegistryValidationError(
                "registry document must be an object"
            )
        fields = frozenset(payload)
        if fields != _ROOT_FIELDS:
            missing = sorted(_ROOT_FIELDS - fields)
            unknown = sorted(fields - _ROOT_FIELDS)
            raise EvidenceSurfaceRegistryValidationError(
                f"registry fields mismatch: missing={missing} unknown={unknown}"
            )
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise EvidenceSurfaceRegistryValidationError(
                f"unsupported registry schema_version {payload.get('schema_version')!r}"
            )
        raw_surfaces = payload.get("surfaces")
        if not isinstance(raw_surfaces, list):
            raise EvidenceSurfaceRegistryValidationError(
                "registry surfaces must be a list"
            )
        return cls(raw_surfaces)

    @classmethod
    def load(
        cls, path: str | Path = DEFAULT_REGISTRY_PATH
    ) -> "EvidenceSurfaceRegistry":
        """Read one registry JSON file and fail closed on any bad content."""

        registry_path = Path(path)
        try:
            text = registry_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise EvidenceSurfaceRegistryError(
                f"cannot read evidence-surface registry {registry_path}: {exc}"
            ) from exc
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise EvidenceSurfaceRegistryValidationError(
                f"invalid registry JSON at {registry_path}: {exc.msg}"
            ) from exc
        return cls.from_dict(payload)

    @property
    def surfaces(self) -> tuple[EvidenceSurface, ...]:
        return self._surfaces

    @property
    def surface_ids(self) -> tuple[str, ...]:
        return tuple(self._by_id)

    @property
    def canonical_hash(self) -> str:
        return canonical_hash(self.to_dict())

    def __len__(self) -> int:
        return len(self._surfaces)

    def __iter__(self) -> Iterator[EvidenceSurface]:
        return iter(self._surfaces)

    def __contains__(self, surface_id: object) -> bool:
        return isinstance(surface_id, str) and surface_id in self._by_id

    def get(self, surface_id: str) -> EvidenceSurface:
        try:
            return self._by_id[surface_id]
        except KeyError as exc:
            raise UnknownEvidenceSurfaceError(
                f"unknown evidence surface {surface_id!r}"
            ) from exc

    def resolve(
        self, surface_ids: Sequence[str] | str
    ) -> tuple[EvidenceSurface, ...]:
        """Resolve references in caller order while rejecting duplicates."""

        raw_ids: Sequence[str]
        if isinstance(surface_ids, str):
            raw_ids = [surface_ids]
        elif isinstance(surface_ids, Sequence):
            raw_ids = surface_ids
        else:
            raise EvidenceSurfaceRegistryValidationError(
                "surface_ids must be a string or sequence of strings"
            )
        seen: set[str] = set()
        resolved: list[EvidenceSurface] = []
        for index, surface_id in enumerate(raw_ids):
            if not isinstance(surface_id, str) or not surface_id.strip():
                raise EvidenceSurfaceRegistryValidationError(
                    f"surface_ids[{index}] must be a non-empty string"
                )
            key = surface_id.strip()
            if key in seen:
                raise EvidenceSurfaceRegistryValidationError(
                    f"duplicate surface reference {key!r}"
                )
            seen.add(key)
            resolved.append(self.get(key))
        return tuple(resolved)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "surfaces": [_surface_dict(surface) for surface in self._surfaces],
        }

    def source_contract(self, surface_id: str) -> dict[str, Any]:
        """Return the static source-contract view and its independent hash."""

        row = _surface_dict(self.get(surface_id))
        contract = {key: row.get(key) for key in _SOURCE_CONTRACT_FIELDS}
        contract["schema_version"] = SCHEMA_VERSION
        contract["source_contract_hash"] = canonical_hash(contract)
        return contract

    def readiness(self, surface_id: str) -> dict[str, Any]:
        """Return only the current readiness view and its independent hash."""

        row = _surface_dict(self.get(surface_id))
        readiness = {key: row.get(key) for key in _READINESS_FIELDS}
        readiness["readiness_hash"] = canonical_hash(readiness)
        return readiness

    def source_contracts(
        self, surface_ids: Sequence[str] | str | None = None
    ) -> tuple[dict[str, Any], ...]:
        surfaces = self._surfaces if surface_ids is None else self.resolve(surface_ids)
        return tuple(self.source_contract(str(surface.surface_id)) for surface in surfaces)

    def readiness_snapshot(
        self, surface_ids: Sequence[str] | str | None = None
    ) -> dict[str, Any]:
        """Build a deterministic readiness view without probing any artifacts."""

        surfaces = self._surfaces if surface_ids is None else self.resolve(surface_ids)
        rows = [self.readiness(str(surface.surface_id)) for surface in surfaces]
        rows.sort(key=lambda row: row["surface_id"])
        snapshot = {
            "schema_version": SCHEMA_VERSION,
            "surface_ids": [row["surface_id"] for row in rows],
            "component_sources": list(
                self.expand_component_sources([row["surface_id"] for row in rows])
            ),
            "gate_ready_surface_ids": [
                row["surface_id"] for row in rows if row["gate_ready"] is True
            ],
            "parked_surface_ids": [
                row["surface_id"]
                for row in rows
                if row.get("saturation_status") == "parked"
            ],
            "frozen_or_saturated_surface_ids": [
                row["surface_id"]
                for row in rows
                if row.get("saturation_status") in {"frozen", "saturated"}
            ],
            "source_contract_not_passed_surface_ids": [
                row["surface_id"]
                for row in rows
                if row.get("source_contract_status") != "pass"
            ],
            "readiness": rows,
        }
        snapshot["readiness_snapshot_hash"] = canonical_hash(snapshot)
        return snapshot

    def component_sources_by_surface(
        self, surface_ids: Sequence[str] | str | None = None
    ) -> dict[str, tuple[str, ...]]:
        """Expose every primary/member source instead of collapsing a join."""

        surfaces = self._surfaces if surface_ids is None else self.resolve(surface_ids)
        out: dict[str, tuple[str, ...]] = {}
        for surface in surfaces:
            row = _surface_dict(surface)
            members = {
                str(item).strip()
                for item in row.get("component_sources") or []
                if str(item).strip()
            }
            primary = str(row.get("data_source") or "").strip()
            if primary:
                members.add(primary)
            out[str(surface.surface_id)] = tuple(sorted(members))
        return out

    def expand_component_sources(
        self, surface_ids: Sequence[str] | str | None = None
    ) -> tuple[str, ...]:
        """Flatten and de-duplicate primary plus component sources."""

        expanded: set[str] = set()
        for members in self.component_sources_by_surface(surface_ids).values():
            expanded.update(members)
        return tuple(sorted(expanded))


def load_evidence_surface_registry(
    path: str | Path = DEFAULT_REGISTRY_PATH,
) -> EvidenceSurfaceRegistry:
    """Functional wrapper for CLI and callers that do not need the class name."""

    return EvidenceSurfaceRegistry.load(path)


def build_evidence_surface_registry(
    surfaces: Iterable[EvidenceSurface | Mapping[str, Any]],
) -> EvidenceSurfaceRegistry:
    """Validate an in-memory surface population."""

    return EvidenceSurfaceRegistry(surfaces)


__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "SCHEMA_VERSION",
    "EvidenceSurfaceRegistry",
    "EvidenceSurfaceRegistryError",
    "EvidenceSurfaceRegistryValidationError",
    "UnknownEvidenceSurfaceError",
    "build_evidence_surface_registry",
    "canonical_hash",
    "load_evidence_surface_registry",
]
