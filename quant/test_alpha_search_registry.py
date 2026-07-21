import json

import pytest

from quant.alpha_search_registry import (
    EvidenceSurfaceRegistry,
    EvidenceSurfaceRegistryValidationError,
    UnknownEvidenceSurfaceError,
    build_evidence_surface_registry,
    load_evidence_surface_registry,
)


def _surface(
    surface_id="sec_flow_join",
    *,
    data_source="sec",
    component_sources=None,
    roles=None,
    pit_status="pit_forward_unsettled",
    evidence_grade="observer",
    settled_count=0,
    gate_ready=False,
    expectation_proxy=None,
    independent_count=None,
    candidate_overlap_count=0,
    saturation_status="unknown",
    reopen_condition=None,
    source_contract_status=None,
    as_of=None,
    artifact_snapshot_hashes=None,
):
    value = {
        "surface_id": surface_id,
        "data_source": data_source,
        "component_sources": component_sources or ["sec", "moomoo_capital_flow"],
        "roles": roles or ["event", "flow"],
        "artifacts": [f"data/non_ohlcv/{surface_id}/manifest.json"],
        "pit_status": pit_status,
        "evidence_grade": evidence_grade,
        "settled_count": settled_count,
        "gate_ready": gate_ready,
        "expectation_proxy": expectation_proxy,
    }
    if independent_count is not None:
        value["independent_count"] = independent_count
    if candidate_overlap_count:
        value["candidate_overlap_count"] = candidate_overlap_count
    if saturation_status != "unknown":
        value["saturation_status"] = saturation_status
    if reopen_condition is not None:
        value["reopen_condition"] = reopen_condition
    if source_contract_status is not None:
        value["source_contract_status"] = source_contract_status
    if as_of is not None:
        value["as_of"] = as_of
    if artifact_snapshot_hashes is not None:
        value["artifact_snapshot_hashes"] = artifact_snapshot_hashes
    return value


def test_registry_loads_strict_surfaces_and_sorts_by_stable_id(tmp_path):
    path = tmp_path / "surfaces.json"
    payload = {
        "schema_version": 1,
        "surfaces": [
            _surface("z_surface"),
            _surface(
                "a_market_prior",
                data_source="polymarket",
                component_sources=["polymarket"],
                roles=["market_expectation"],
                expectation_proxy={
                    "type": "direct_implied",
                    "field": "probability",
                    "source": "polymarket",
                },
            ),
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    registry = load_evidence_surface_registry(path)

    assert registry.surface_ids == ("a_market_prior", "z_surface")
    assert registry.to_dict()["schema_version"] == 1
    assert len(registry.canonical_hash) == 64
    assert registry.get("a_market_prior").expectation_proxy["field"] == "probability"


def test_join_components_are_expanded_individually_not_collapsed():
    registry = build_evidence_surface_registry(
        [
            _surface(
                component_sources=["sec", "moomoo_capital_flow", "ortex_borrow"]
            ),
            _surface(
                "price_context",
                data_source="moomoo_price",
                component_sources=["moomoo_price"],
            ),
        ]
    )

    assert registry.component_sources_by_surface("sec_flow_join") == {
        "sec_flow_join": ("moomoo_capital_flow", "ortex_borrow", "sec")
    }
    assert registry.expand_component_sources(
        ["sec_flow_join", "price_context"]
    ) == ("moomoo_capital_flow", "moomoo_price", "ortex_borrow", "sec")


def test_source_contract_and_readiness_have_independent_hashes():
    before = EvidenceSurfaceRegistry([_surface(settled_count=0)])
    after = EvidenceSurfaceRegistry([_surface(settled_count=7)])

    before_contract = before.source_contract("sec_flow_join")
    after_contract = after.source_contract("sec_flow_join")
    before_readiness = before.readiness("sec_flow_join")
    after_readiness = after.readiness("sec_flow_join")

    assert before_contract["source_contract_hash"] == after_contract["source_contract_hash"]
    assert before_readiness["readiness_hash"] != after_readiness["readiness_hash"]
    assert "settled_count" not in before_contract
    assert "artifacts" not in before_readiness


def test_extended_surface_fields_roundtrip_into_the_correct_views():
    registry = EvidenceSurfaceRegistry(
        [
            _surface(
                "parked_join",
                independent_count=8,
                settled_count=3,
                candidate_overlap_count=2,
                saturation_status="parked",
                reopen_condition={"independent_count_gte": 20},
                source_contract_status="partial",
                as_of="2026-07-21T12:00:00Z",
                artifact_snapshot_hashes={
                    "data/non_ohlcv/parked_join/manifest.json": "b" * 64
                },
            )
        ]
    )

    reloaded = EvidenceSurfaceRegistry.from_dict(registry.to_dict())
    contract = reloaded.source_contract("parked_join")
    readiness = reloaded.readiness("parked_join")

    assert reloaded.canonical_hash == registry.canonical_hash
    assert "source_contract_status" not in contract
    assert "as_of" not in contract
    assert "artifact_snapshot_hashes" not in contract
    assert readiness["independent_count"] == 8
    assert readiness["settled_count"] == 3
    assert readiness["candidate_overlap_count"] == 2
    assert readiness["saturation_status"] == "parked"
    assert readiness["reopen_condition"] == {"independent_count_gte": 20}
    assert readiness["as_of"] == "2026-07-21T12:00:00Z"
    assert readiness["artifact_snapshot_hashes"] == {
        "data/non_ohlcv/parked_join/manifest.json": "b" * 64
    }
    assert readiness["source_contract_status"] == "partial"
    assert "saturation_status" not in contract


def test_source_contract_status_changes_readiness_not_source_identity():
    partial = EvidenceSurfaceRegistry([_surface(source_contract_status="partial")])
    passing = EvidenceSurfaceRegistry([_surface(source_contract_status="pass")])

    assert (
        partial.source_contract("sec_flow_join")["source_contract_hash"]
        == passing.source_contract("sec_flow_join")["source_contract_hash"]
    )
    assert (
        partial.readiness("sec_flow_join")["readiness_hash"]
        != passing.readiness("sec_flow_join")["readiness_hash"]
    )


def test_readiness_snapshot_does_not_flag_a_passing_source_contract():
    registry = EvidenceSurfaceRegistry([_surface(source_contract_status="pass")])

    snapshot = registry.readiness_snapshot()

    assert snapshot["source_contract_not_passed_surface_ids"] == []
    assert snapshot["readiness"][0]["source_contract_status"] == "pass"


def test_component_change_changes_source_contract_hash():
    before = EvidenceSurfaceRegistry([_surface(component_sources=["sec", "moomoo"])])
    after = EvidenceSurfaceRegistry(
        [_surface(component_sources=["sec", "moomoo", "ortex"])]
    )

    assert (
        before.source_contract("sec_flow_join")["source_contract_hash"]
        != after.source_contract("sec_flow_join")["source_contract_hash"]
    )


def test_readiness_snapshot_is_deterministic_and_does_not_probe_artifacts():
    registry = EvidenceSurfaceRegistry(
        [
            _surface("observer"),
            _surface(
                "gate_ready",
                data_source="warehouse",
                component_sources=["warehouse"],
                pit_status="canonical_pit",
                evidence_grade="gate_candidate",
                settled_count=25,
                independent_count=25,
                candidate_overlap_count=3,
                gate_ready=True,
                source_contract_status="pass",
                as_of="2026-07-21T12:00:00Z",
                artifact_snapshot_hashes={
                    "data/non_ohlcv/gate_ready/manifest.json": "a" * 64
                },
            ),
        ]
    )

    first = registry.readiness_snapshot()
    second = registry.readiness_snapshot(["gate_ready", "observer"])

    assert first == second
    assert first["gate_ready_surface_ids"] == ["gate_ready"]
    assert first["component_sources"] == ["moomoo_capital_flow", "sec", "warehouse"]
    assert len(first["readiness_snapshot_hash"]) == 64


def test_unknown_and_duplicate_surface_references_fail_closed():
    registry = EvidenceSurfaceRegistry([_surface()])

    with pytest.raises(UnknownEvidenceSurfaceError, match="missing"):
        registry.get("missing")
    with pytest.raises(EvidenceSurfaceRegistryValidationError, match="duplicate"):
        registry.resolve(["sec_flow_join", "sec_flow_join"])


def test_duplicate_surface_id_fails_closed():
    with pytest.raises(EvidenceSurfaceRegistryValidationError, match="duplicate surface_id"):
        EvidenceSurfaceRegistry([_surface(), _surface()])


@pytest.mark.parametrize(
    "payload,match",
    [
        ({"schema_version": 1, "surfaces": [], "unknown": True}, "unknown"),
        ({"schema_version": 2, "surfaces": []}, "schema_version"),
        ({"schema_version": 1, "surfaces": {}}, "must be a list"),
    ],
)
def test_registry_root_schema_is_strict(payload, match):
    with pytest.raises(EvidenceSurfaceRegistryValidationError, match=match):
        EvidenceSurfaceRegistry.from_dict(payload)


def test_surface_contract_validation_error_is_path_qualified():
    invalid = _surface(
        "bad_prior",
        roles=["market_expectation"],
        expectation_proxy=None,
    )

    with pytest.raises(
        EvidenceSurfaceRegistryValidationError,
        match=r"surfaces\[0\].*expectation_proxy",
    ):
        EvidenceSurfaceRegistry([invalid])
