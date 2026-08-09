from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path

import pytest

import quant.alpha_search_engine as engine
from quant.alpha_search_contract import (
    HypothesisCandidate,
    research_only_production_impact,
)
from quant.alpha_search_engine import (
    AlphaSearchError,
    build_failure_taxonomy,
    build_search_report,
    build_selection_scope_manifest,
    evaluate_preflight,
    freeze_selection_panel,
    outcome_field_paths,
    select_diverse_candidates,
    stable_hash,
    verify_selection_panel,
)
from quant.alpha_search_registry import EvidenceSurfaceRegistry
from quant.alpha_search_history import (
    build_historical_prior_snapshot,
    candidate_legacy_fingerprints,
)


PREREGISTERED_AT = "2026-07-20T15:00:00Z"
DATA_CUTOFF = "2026-07-20T15:15:00Z"
CREATED_AT = "2026-07-20T15:30:00Z"
FREEZE_AT = "2026-07-20T16:00:00Z"


def _build_test_history_snapshot() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "frozen.jsonl"
        path.write_text(
            json.dumps(
                {
                    "family_key": "unrelated_historical_family",
                    "fingerprint": {
                        "data_source": "unrelated_source",
                        "field_tags": ["unrelated"],
                        "gate_shape": "other",
                    },
                    "representative_exps": ["exp-20260719-001"],
                    "status": "single_attempt",
                    "reopen_condition": None,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return build_historical_prior_snapshot(
            path,
            history_cutoff="2026-07-20T14:59:00Z",
            isolated_fixture=True,
        )


TEST_HISTORY_SNAPSHOT = _build_test_history_snapshot()


def _surface(
    surface_id: str,
    source: str,
    *,
    roles: list[str],
    proxy_type: str | None = None,
    grade: str = "gate_candidate",
    pit: str | None = None,
    saturation: str = "open",
    source_status: str = "pass",
    as_of: str = "2026-07-20T14:00:00Z",
) -> dict:
    artifact = f"data/test/{surface_id}.json"
    gate_ready = grade == "gate_candidate"
    pit_status = pit or {
        "lead": "snapshot_only",
        "observer": "pit_forward_unsettled",
        "observed_only": "settled_forward_sufficient",
        "gate_candidate": "canonical_pit",
    }[grade]
    result = {
        "surface_id": surface_id,
        "data_source": source,
        "component_sources": [source],
        "roles": roles,
        "artifacts": [artifact],
        "pit_status": pit_status,
        "evidence_grade": grade,
        "settled_count": 40 if grade in {"observed_only", "gate_candidate"} else 0,
        "independent_count": 40,
        "candidate_overlap_count": 10,
        "gate_ready": gate_ready,
        "expectation_proxy": (
            {"type": proxy_type, "field": "probability", "source": source}
            if proxy_type
            else None
        ),
        "saturation_status": saturation,
        "reopen_condition": (
            {"independent_count_gte": 80} if saturation == "parked" else None
        ),
        "source_contract_status": source_status,
        "as_of": as_of,
        "artifact_snapshot_hashes": {artifact: stable_hash({"surface": surface_id})},
    }
    if pit_status == "research_pit":
        result["research_pit_basis"] = (
            "row event_time is vendor supplied; as-known vintage revisions are unverified"
        )
        result["known_future_leakage"] = False
    return result


def _surfaces(
    *,
    prior_grade: str = "gate_candidate",
    prior_pit: str | None = None,
) -> EvidenceSurfaceRegistry:
    return EvidenceSurfaceRegistry.from_dict(
        {
            "schema_version": 1,
            "surfaces": [
                _surface(
                    "market-prior",
                    "prediction_market",
                    roles=["market_expectation", "event_probability"],
                    proxy_type="direct_implied_probability",
                    grade=prior_grade,
                    pit=prior_pit,
                ),
                _surface(
                    "independent-fact",
                    "official_filings",
                    roles=["independent_evidence", "official_event"],
                ),
            ],
        }
    )


def _candidate(
    label: str = "a",
    queue: str = "exploration",
    *,
    created_at: str = CREATED_AT,
    grade: str = "observer",
) -> dict:
    raw = {
        "schema_version": 1,
        "candidate_kind": "expectation_gap",
        "candidate_id": "pending",
        "search_queue": queue,
        "title": f"Observable prior versus filing evidence {label}",
        "created_at": created_at,
        "created_by": "alpha-search-test",
        "hypothesis": f"A verifiable filing changes probability before equity reprices ({label}).",
        "fingerprint": {
            "data_source": "prediction_market",
            "component_sources": ["prediction_market", "official_filings"],
            "expectation_proxy": "direct_implied_probability",
            "economic_mechanism": f"policy_probability_repricing_{label}",
            "decision_surface": "candidate_pool",
            "payoff_shape": "event_drift",
            "horizon": "H5-H20",
            "execution_dependency": "liquid_cash_equity",
            "portfolio_role": "orthogonal_event_sleeve",
        },
        "surface_ids": ["market-prior", "independent-fact"],
        "expectation_gap": {
            "market_prior": {
                "observable": True,
                "proxy_type": "direct_implied_probability",
                "source": "prediction_market",
                "known_at": "2026-07-20T14:00:00Z",
                "value": 0.42,
                "units": "probability",
                "provenance": "timestamped quote",
            },
            "independent_evidence": [
                {
                    "evidence_id": f"fact-{label}",
                    "source": "official_filings",
                    "known_at": "2026-07-20T14:05:00Z",
                    "state": "condition satisfied",
                    "provenance": "timestamped filing",
                }
            ],
            "gap_definition": "calibrated filing state probability minus quoted probability",
            "our_posterior": {
                "value": 0.61,
                "method": "frozen_calibrator_v1",
                "calibration_reference": "calibration-scope-v1",
                "known_at": "2026-07-20T14:06:00Z",
            },
            "transmission": {
                "affected_tickers": ["AAA"],
                "expected_direction": "positive",
                "catalyst": "formal decision",
                "half_life": "10 sessions",
                "causal_steps": ["filing", "probability update", "cash-flow repricing"],
            },
        },
        "why_not_arbitraged": "Mapping and timing require structured cross-source evidence.",
        "falsifier": "No monotone repricing after timestamp-safe event alignment.",
        "baseline": {"universe": ["AAA"], "policy": "cash"},
        "treatment": {"policy": "frozen event candidate rule"},
        "replacement_value_comparator": "cash, SPY, QQQ, and current core opportunity cost",
        "expected_horizon": "H5-H20",
        "execution_envelope": {
            "intended_instrument": "cash equity",
            "liquidity_dependency": "ADV floor",
            "costs_and_carry": "fixed bps model",
            "borrow_dependency": "none",
            "capacity_constraint": "paper cap",
            "timing_constraint": "next session open",
            "trade_enabled": False,
            "orders_enabled": False,
            "live_ready": False,
        },
        "evidence_grade": grade,
        "production_impact": research_only_production_impact(),
    }
    return HypothesisCandidate.with_computed_id(raw).to_dict()


PARENT_SCOPE_ID = "scope-" + "1" * 24


def _lineage_parent() -> dict:
    return engine._bind_candidate_readiness(
        _candidate(created_at="2026-07-20T14:30:00Z"),
        _surfaces(),
    )


def _amended_candidate(
    parent: dict,
    *,
    parent_scope_id: str = PARENT_SCOPE_ID,
    attachment_suffix: str = "v1",
    attachment_role: str = "comparator",
    declared_at: str = CREATED_AT,
) -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    if attachment_role == "comparator":
        attachment_path = (
            repo_root
            / "data/experiments/exp-20260729-004/test_comparator_allocation_v1.json"
        )
        attachment_field = "baseline.comparator_allocation_attachment"
        attachment_hash_field = "baseline.comparator_allocation_attachment_hash"
        attachment_container = raw_container = "baseline"
        attachment_key = "comparator_allocation_attachment"
        attachment_hash_key = "comparator_allocation_attachment_hash"
    elif attachment_role == "endpoint":
        attachment_path = (
            repo_root
            / "data/experiments/exp-20260729-004/test_endpoint_preflight_v1.json"
        )
        attachment_field = "treatment.endpoint_preflight_attachment"
        attachment_hash_field = "treatment.endpoint_preflight_attachment_hash"
        attachment_container = raw_container = "treatment"
        attachment_key = "endpoint_preflight_attachment"
        attachment_hash_key = "endpoint_preflight_attachment_hash"
    else:
        raise ValueError(f"unsupported attachment_role: {attachment_role}")
    attachment_locator = attachment_path.relative_to(repo_root).as_posix()
    attachment_hash = hashlib.sha256(attachment_path.read_bytes()).hexdigest()
    raw = copy.deepcopy(parent)
    raw["candidate_id"] = "pending"
    raw["created_at"] = declared_at
    raw["created_by"] = "alpha-search-amendment-test"
    raw[attachment_container][attachment_key] = attachment_locator
    raw[raw_container][attachment_hash_key] = attachment_hash
    raw["next_machine_action"] = (
        f"verify the bound evaluation attachments ({attachment_suffix})"
    )
    raw["amendment_lineage"] = {
        "parent_candidate_id": parent["candidate_id"],
        "parent_candidate_snapshot": copy.deepcopy(parent),
        "parent_candidate_snapshot_hash": stable_hash(parent),
        "parent_selection_scope_id": parent_scope_id,
        "amendment_reason": "outcome_blind_contract_completion",
        "changed_fields": [
            attachment_field,
            attachment_hash_field,
            "next_machine_action",
        ],
        "parent_outcome_accessed": False,
        "parent_experiment_id": None,
        "declared_at": declared_at,
    }
    return HypothesisCandidate.with_computed_id(raw).to_dict()


def _history_with_parent(
    parent: dict,
    *,
    include_other_neighbor: bool = False,
    competing_child: dict | None = None,
    abandoned_candidate: dict | None = None,
    reserved_family_row: dict | None = None,
) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        frozen = root / "frozen.jsonl"
        fingerprint = {
            "data_source": "unrelated_source",
            "field_tags": ["unrelated"],
            "gate_shape": "other",
        }
        family_key = "unrelated_historical_family"
        if include_other_neighbor:
            fingerprint = candidate_legacy_fingerprints(parent)[0]
            family_key = "other_blocking_candidate_family"
        frozen_rows = [
            {
                "family_key": family_key,
                "fingerprint": fingerprint,
                "representative_exps": ["exp-20260719-001"],
                "status": "single_attempt",
                "reopen_condition": None,
            }
        ]
        if reserved_family_row is not None:
            frozen_rows.append(reserved_family_row)
        frozen.write_text(
            "".join(json.dumps(row) + "\n" for row in frozen_rows),
            encoding="utf-8",
        )
        events = root / "events.jsonl"
        event_rows = [
            {
                "record_type": "candidate_snapshot",
                "recorded_at": "2026-07-20T14:45:00Z",
                "identity": {
                    "candidate_id": parent["candidate_id"],
                    "selection_scope_id": PARENT_SCOPE_ID,
                },
                "payload": parent,
            }
        ]
        if abandoned_candidate is not None:
            event_rows.append(
                {
                    "record_type": "candidate_snapshot",
                    "recorded_at": "2026-07-20T14:20:00Z",
                    "identity": {
                        "candidate_id": abandoned_candidate["candidate_id"],
                        "selection_scope_id": "scope-" + "3" * 24,
                    },
                    "payload": abandoned_candidate,
                }
            )
        if competing_child is not None:
            event_rows.append(
                {
                    "record_type": "candidate_snapshot",
                    "recorded_at": "2026-07-20T14:55:00Z",
                    "identity": {
                        "candidate_id": competing_child["candidate_id"],
                        "selection_scope_id": "scope-" + "4" * 24,
                    },
                    "payload": competing_child,
                }
            )
        events.write_text(
            "".join(json.dumps(row) + "\n" for row in event_rows),
            encoding="utf-8",
        )
        return build_historical_prior_snapshot(
            frozen,
            history_cutoff="2026-07-20T14:59:00Z",
            discovery_ledgers=[events],
            isolated_fixture=True,
        )


@pytest.fixture
def trusted_lineage_history(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate D3 lineage mechanics from repository-anchor integration tests."""

    monkeypatch.setattr(
        engine,
        "_validate_repository_lineage_history",
        lambda value: value,
    )


def _manifest(
    surfaces: EvidenceSurfaceRegistry,
    *,
    queue_budgets: dict[str, int] | None = None,
    expected_count: int = 1,
    selection_limit: int = 1,
    batch_policy_bundle_id: str | None = None,
    prior_fingerprints=None,
) -> dict:
    prior_fingerprints = (
        copy.deepcopy(TEST_HISTORY_SNAPSHOT)
        if prior_fingerprints is None
        else prior_fingerprints
    )
    return build_selection_scope_manifest(
        scope_name="phase1-test-scope",
        preregistered_at=PREREGISTERED_AT,
        data_cutoff=DATA_CUTOFF,
        freeze_at=FREEZE_AT,
        generator_version="test-generator-v1",
        candidate_generation_config={
            "queues": ["exploration", "adjacent", "exploitation"],
            "outcome_fields_allowed": False,
        },
        allowed_surface_ids=list(surfaces.surface_ids),
        surface_registry_hash=surfaces.canonical_hash,
        prior_fingerprints=prior_fingerprints,
        queue_budgets=queue_budgets
        or {"exploration": 1, "adjacent": 0, "exploitation": 0},
        expected_candidate_count=expected_count,
        selection_limit=selection_limit,
        batch_policy_bundle_id=batch_policy_bundle_id,
    )


def _panel(
    candidates: list[dict] | None = None,
    *,
    surfaces: EvidenceSurfaceRegistry | None = None,
    manifest: dict | None = None,
    prior_fingerprints=None,
) -> tuple[dict, EvidenceSurfaceRegistry, dict, object]:
    candidates = [_candidate()] if candidates is None else candidates
    surfaces = _surfaces() if surfaces is None else surfaces
    prior_fingerprints = (
        copy.deepcopy(TEST_HISTORY_SNAPSHOT)
        if prior_fingerprints is None
        else prior_fingerprints
    )
    manifest = _manifest(surfaces, prior_fingerprints=prior_fingerprints) if manifest is None else manifest
    panel = freeze_selection_panel(
        candidates,
        surfaces,
        scope_manifest=manifest,
        selection_pool_complete=True,
        prior_fingerprints=prior_fingerprints,
    )
    return panel, surfaces, manifest, prior_fingerprints


def _strict_verify(panel: dict, surfaces, manifest, priors) -> dict:
    return verify_selection_panel(
        panel,
        surfaces=surfaces,
        scope_manifest=manifest,
        prior_fingerprints=priors,
        require_external_context=True,
    )


def test_outcome_audit_rejects_nested_realized_results_but_allows_expected_payoff() -> None:
    clean = _candidate()
    clean["prediction"] = {
        "success_probability": 0.2,
        "main_failure_modes": ["already_priced"],
        "confidence_reason": "ex ante estimate",
    }
    assert outcome_field_paths(clean) == []
    clean["prediction"]["post_event_return"] = 0.2
    assert outcome_field_paths(clean) == ["candidate.prediction.post_event_return"]


def test_scope_manifest_uses_contract_recursive_outcome_audit() -> None:
    surfaces = _surfaces()
    kwargs = {
        "scope_name": "outcome-contaminated-scope",
        "preregistered_at": PREREGISTERED_AT,
        "data_cutoff": DATA_CUTOFF,
        "freeze_at": FREEZE_AT,
        "generator_version": "test-generator-v1",
        "candidate_generation_config": {"outcome": 1},
        "allowed_surface_ids": list(surfaces.surface_ids),
        "surface_registry_hash": surfaces.canonical_hash,
        "prior_fingerprints": copy.deepcopy(TEST_HISTORY_SNAPSHOT),
        "queue_budgets": {
            "exploration": 1,
            "adjacent": 0,
            "exploitation": 0,
        },
        "expected_candidate_count": 1,
    }
    with pytest.raises(AlphaSearchError) as built:
        build_selection_scope_manifest(**kwargs)
    assert built.value.code == "forbidden_outcome_field"

    forged = _manifest(surfaces)
    forged["candidate_generation_config"] = {"outcome": 1}
    forged["manifest_hash"] = engine._hash_without_top_level(
        forged, "manifest_hash"
    )
    with pytest.raises(AlphaSearchError) as validated:
        engine.validate_selection_scope_manifest(forged)
    assert validated.value.code == "forbidden_outcome_field"


def test_preflight_passes_complete_contract_and_is_hash_stable() -> None:
    first = evaluate_preflight(_candidate(), _surfaces(), data_cutoff=DATA_CUTOFF)
    second = evaluate_preflight(_candidate(), _surfaces(), data_cutoff=DATA_CUTOFF)
    assert first["decision"] == "pass"
    assert all(gate["status"] == "pass" for gate in first["gates"].values())
    assert first["preflight_hash"] == second["preflight_hash"]
    assert first["outcome_blind"] is True


def test_cutoff_rejects_future_prior_and_invalidates_scope() -> None:
    candidate = _candidate()
    candidate["expectation_gap"]["market_prior"]["known_at"] = "2099-01-01T00:00:00Z"
    candidate = HypothesisCandidate.with_computed_id(candidate).to_dict()
    result = evaluate_preflight(candidate, _surfaces(), data_cutoff=DATA_CUTOFF)
    assert result["decision"] == "reject"
    assert result["outcome_blind"] is False
    assert "outcome_contamination" in result["failure_reasons"]

    surfaces = _surfaces()
    manifest = _manifest(surfaces)
    with pytest.raises(AlphaSearchError, match="outcome_contamination"):
        freeze_selection_panel(
            [candidate],
            surfaces,
            scope_manifest=manifest,
            selection_pool_complete=True,
            prior_fingerprints=copy.deepcopy(TEST_HISTORY_SNAPSHOT),
        )


def test_unrelated_gate_surface_cannot_upgrade_weak_actual_prior() -> None:
    surfaces = _surfaces(prior_grade="observer")
    candidate = _candidate(grade="observed_only")
    result = evaluate_preflight(candidate, surfaces, data_cutoff=DATA_CUTOFF)
    assert result["decision"] == "park"
    assert result["maximum_supported_evidence_grade"] == "observer"
    assert "insufficient_independent_rows" in result["failure_reasons"]


def test_research_pit_candidate_passes_d0_d3_and_can_be_selected_for_replay() -> None:
    surfaces = _surfaces(prior_grade="lead", prior_pit="research_pit")
    candidate = _candidate(grade="lead")
    preflight = evaluate_preflight(candidate, surfaces, data_cutoff=DATA_CUTOFF)

    assert preflight["decision"] == "pass"
    assert preflight["maximum_supported_evidence_grade"] == "lead"
    assert preflight["outcome_blind"] is True
    score = engine.score_candidate(candidate, preflight)
    assert score["components"]["evidence_maturity"] == 0.0
    assert select_diverse_candidates(
        [candidate],
        {candidate["candidate_id"]: preflight},
        {candidate["candidate_id"]: score},
        limit=1,
    ) == [candidate["candidate_id"]]


def test_raw_mapping_surface_must_pass_contract_before_d0_or_selection() -> None:
    registry = _surfaces()
    raw_surfaces = registry.to_dict()
    prior = next(
        row for row in raw_surfaces["surfaces"] if row["surface_id"] == "market-prior"
    )
    prior["pit_status"] = "research_pit"
    prior["evidence_grade"] = "gate_candidate"
    prior["gate_ready"] = True
    prior.pop("research_pit_basis", None)
    prior.pop("known_future_leakage", None)
    prior.pop("source_contract_status", None)
    candidate = _candidate()
    candidate["candidate_id"] = "pending"
    candidate["evidence_grade"] = "gate_candidate"
    candidate["source_readiness_snapshot"] = [
        {
            "surface_id": row["surface_id"],
            "snapshot_hash": stable_hash(row),
        }
        for row in sorted(raw_surfaces["surfaces"], key=lambda row: row["surface_id"])
    ]
    candidate = HypothesisCandidate.with_computed_id(candidate).to_dict()

    with pytest.raises(AlphaSearchError) as preflight_error:
        evaluate_preflight(candidate, raw_surfaces, data_cutoff=DATA_CUTOFF)
    assert preflight_error.value.code == "invalid_evidence_surface"

    # Reproduce a caller that preregistered the unvalidated raw mapping's hash.
    # Panel freezing must still validate the rows instead of trusting that hash.
    manifest = _manifest(registry)
    manifest["surface_registry_hash"] = stable_hash(
        {
            "schema_version": 1,
            "surfaces": sorted(
                raw_surfaces["surfaces"], key=lambda row: row["surface_id"]
            ),
        }
    )
    manifest["manifest_hash"] = engine._hash_without_top_level(
        manifest, "manifest_hash"
    )
    with pytest.raises(AlphaSearchError) as selection_error:
        freeze_selection_panel(
            [candidate],
            raw_surfaces,
            scope_manifest=manifest,
            selection_pool_complete=True,
            prior_fingerprints=copy.deepcopy(TEST_HISTORY_SNAPSHOT),
        )
    assert selection_error.value.code == "invalid_evidence_surface"


def test_valid_raw_research_pit_lead_can_pass_and_be_selected() -> None:
    registry = _surfaces(prior_grade="lead", prior_pit="research_pit")
    raw_surfaces = registry.to_dict()
    candidate = _candidate(grade="lead")
    preflight = evaluate_preflight(candidate, raw_surfaces, data_cutoff=DATA_CUTOFF)

    assert preflight["decision"] == "pass"
    assert preflight["maximum_supported_evidence_grade"] == "lead"
    panel = freeze_selection_panel(
        [candidate],
        raw_surfaces,
        scope_manifest=_manifest(registry),
        selection_pool_complete=True,
        prior_fingerprints=copy.deepcopy(TEST_HISTORY_SNAPSHOT),
    )
    assert panel["selected_candidate_ids"] == [candidate["candidate_id"]]


def test_gate_candidate_on_research_pit_surface_parks() -> None:
    surfaces = _surfaces(prior_grade="lead", prior_pit="research_pit")
    candidate = _candidate(grade="lead")
    candidate["evidence_grade"] = "gate_candidate"
    result = evaluate_preflight(candidate, surfaces, data_cutoff=DATA_CUTOFF)

    assert result["decision"] == "park"
    assert result["maximum_supported_evidence_grade"] == "lead"
    assert "insufficient_independent_rows" in result["failure_reasons"]


def test_known_future_leakage_surface_is_rejected_even_if_other_fields_pass() -> None:
    surfaces = _surfaces(prior_grade="lead", prior_pit="research_pit").to_dict()
    prior = next(
        row for row in surfaces["surfaces"] if row["surface_id"] == "market-prior"
    )
    prior["known_future_leakage"] = True
    prior["pit_status"] = "not_pit"
    prior["evidence_grade"] = "lead"
    prior["gate_ready"] = False
    prior.pop("research_pit_basis", None)
    registry = EvidenceSurfaceRegistry.from_dict(surfaces)
    candidate = _candidate(grade="lead")
    result = evaluate_preflight(candidate, registry, data_cutoff=DATA_CUTOFF)

    assert result["decision"] == "reject"
    assert result["outcome_blind"] is False
    assert any(
        reason.startswith("surface_known_future_leakage:")
        for reason in result["gates"]["D0"]["reasons"]
    )


def test_every_component_requires_declared_unambiguous_primary_row() -> None:
    candidate = _candidate()
    candidate["fingerprint"]["component_sources"].append("unregistered_vendor")
    result = evaluate_preflight(candidate, _surfaces(), data_cutoff=DATA_CUTOFF)
    assert result["decision"] == "reject"
    assert "component_source_not_registered:unregistered_vendor" in result["gates"]["D0"]["reasons"]

    undeclared = _candidate()
    undeclared["surface_ids"] = ["market-prior"]
    result = evaluate_preflight(undeclared, _surfaces(), data_cutoff=DATA_CUTOFF)
    assert result["decision"] == "reject"
    assert any(
        reason.startswith("component_primary_surface_not_declared:official_filings")
        for reason in result["gates"]["D0"]["reasons"]
    )


def test_plain_event_harder_reject_freezes_as_zero_selection_panel() -> None:
    candidate = _candidate(grade="lead")
    candidate["candidate_kind"] = "plain_event_lead"
    candidate["expectation_gap"] = None
    candidate["fingerprint"]["expectation_proxy"] = "unidentified"
    candidate["fingerprint"]["component_sources"].append("unregistered_vendor")
    candidate = HypothesisCandidate.with_computed_id(candidate).to_dict()
    surfaces = _surfaces()
    history = copy.deepcopy(TEST_HISTORY_SNAPSHOT)
    manifest = _manifest(surfaces, prior_fingerprints=history)

    panel = freeze_selection_panel(
        [candidate],
        surfaces,
        scope_manifest=manifest,
        selection_pool_complete=True,
        prior_fingerprints=history,
    )

    preflight = panel["preflight_decisions"][candidate["candidate_id"]]
    assert preflight["decision"] == "reject"
    assert preflight["gates"]["D0"]["status"] == "reject"
    assert preflight["gates"]["D1"]["status"] == "park"
    assert "market_expectation_unidentified" in preflight["failure_reasons"]
    assert panel["selected_candidate_ids"] == []
    assert panel["selected_candidate_id"] is None
    assert _strict_verify(panel, surfaces, manifest, history)["valid"] is True


def test_parked_component_primary_blocks_join() -> None:
    surfaces = EvidenceSurfaceRegistry.from_dict(
        {
            "schema_version": 1,
            "surfaces": [
                *_surfaces().to_dict()["surfaces"],
                _surface(
                    "parked-member",
                    "parked_member",
                    roles=["independent_evidence"],
                    grade="observer",
                    saturation="parked",
                ),
            ],
        }
    )
    candidate = _candidate()
    candidate["fingerprint"]["component_sources"].append("parked_member")
    candidate["surface_ids"].append("parked-member")
    result = evaluate_preflight(candidate, surfaces, data_cutoff=DATA_CUTOFF)
    assert result["decision"] == "reject"
    assert "component_surface_parked:parked-member" in result["gates"]["D3"]["reasons"]


def test_prior_fingerprint_anchor_prevents_empty_history_bypass() -> None:
    candidate = _candidate()
    surfaces = _surfaces()
    history = copy.deepcopy(TEST_HISTORY_SNAPSHOT)
    manifest = _manifest(surfaces, prior_fingerprints=history)

    with pytest.raises(AlphaSearchError, match="prior_fingerprint_snapshot_mismatch"):
        freeze_selection_panel(
            [candidate],
            surfaces,
            scope_manifest=manifest,
            selection_pool_complete=True,
            prior_fingerprints=[],
        )

    panel = freeze_selection_panel(
        [candidate],
        surfaces,
        scope_manifest=manifest,
        selection_pool_complete=True,
        prior_fingerprints=history,
    )
    assert panel["preflight_decisions"][candidate["candidate_id"]]["decision"] == "pass"


def test_depth_one_amendment_waives_only_authenticated_parent_and_reverifies(
    trusted_lineage_history: None,
) -> None:
    parent = _lineage_parent()
    candidate = _amended_candidate(parent)
    history = _history_with_parent(parent)
    surfaces = _surfaces()
    manifest = _manifest(surfaces, prior_fingerprints=history)

    panel = freeze_selection_panel(
        [candidate],
        surfaces,
        scope_manifest=manifest,
        selection_pool_complete=True,
        prior_fingerprints=history,
    )

    preflight = panel["preflight_decisions"][candidate["candidate_id"]]
    assert preflight["decision"] == "pass"
    assert preflight["gates"]["D3"] == {"status": "pass", "reasons": []}
    assert panel["selected_candidate_id"] == candidate["candidate_id"]
    assert _strict_verify(panel, surfaces, manifest, history)["valid"] is True
    parent_metadata = {
        json.dumps(record["candidate_metadata"], sort_keys=True)
        for record in history["records"]
        if record.get("family_key") == parent["candidate_id"]
    }
    assert parent_metadata
    assert all(stable_hash(parent) in value for value in parent_metadata)


def test_endpoint_attachment_uses_typed_outcome_blind_schema(
    trusted_lineage_history: None,
) -> None:
    parent = _lineage_parent()
    candidate = _amended_candidate(parent, attachment_role="endpoint")
    history = _history_with_parent(parent)

    preflight = evaluate_preflight(
        candidate,
        _surfaces(),
        prior_fingerprints=history,
        data_cutoff=DATA_CUTOFF,
        evaluated_at=FREEZE_AT,
        selection_scope_id="scope-" + "2" * 24,
    )

    assert preflight["outcome_blind"] is True
    assert preflight["gates"]["D3"] == {"status": "pass", "reasons": []}


def test_amendment_requires_parent_in_complete_bound_history(
    trusted_lineage_history: None,
) -> None:
    parent = _lineage_parent()
    candidate = _amended_candidate(parent)
    history = copy.deepcopy(TEST_HISTORY_SNAPSHOT)
    surfaces = _surfaces()
    manifest = _manifest(surfaces, prior_fingerprints=history)

    panel = freeze_selection_panel(
        [candidate],
        surfaces,
        scope_manifest=manifest,
        selection_pool_complete=True,
        prior_fingerprints=history,
    )

    preflight = panel["preflight_decisions"][candidate["candidate_id"]]
    assert preflight["decision"] == "reject"
    assert "amendment_parent_missing_from_history" in preflight["gates"]["D3"]["reasons"]
    assert panel["selected_candidate_id"] is None


def test_amendment_does_not_waive_another_blocking_neighbor(
    trusted_lineage_history: None,
) -> None:
    parent = _lineage_parent()
    candidate = _amended_candidate(parent)
    history = _history_with_parent(parent, include_other_neighbor=True)
    surfaces = _surfaces()
    manifest = _manifest(surfaces, prior_fingerprints=history)

    panel = freeze_selection_panel(
        [candidate],
        surfaces,
        scope_manifest=manifest,
        selection_pool_complete=True,
        prior_fingerprints=history,
    )

    preflight = panel["preflight_decisions"][candidate["candidate_id"]]
    assert preflight["decision"] == "reject"
    assert any(
        "exp-20260719-001" in reason
        for reason in preflight["gates"]["D3"]["reasons"]
    )


def test_amendment_rejects_competing_depth_one_child(
    trusted_lineage_history: None,
) -> None:
    parent = _lineage_parent()
    competing = _amended_candidate(
        parent,
        attachment_suffix="prior-child",
        declared_at="2026-07-20T14:50:00Z",
    )
    candidate = _amended_candidate(parent, attachment_suffix="current-child")
    history = _history_with_parent(parent, competing_child=competing)
    surfaces = _surfaces()
    manifest = _manifest(surfaces, prior_fingerprints=history)

    panel = freeze_selection_panel(
        [candidate],
        surfaces,
        scope_manifest=manifest,
        selection_pool_complete=True,
        prior_fingerprints=history,
    )

    reasons = panel["preflight_decisions"][candidate["candidate_id"]]["gates"]["D3"]["reasons"]
    assert f"amendment_competing_child:{competing['candidate_id']}" in reasons
    assert panel["selected_candidate_id"] is None


def test_amendment_semantic_rewrite_fails_even_with_valid_parent_binding(
    trusted_lineage_history: None,
) -> None:
    parent = _lineage_parent()
    forged = _amended_candidate(parent)
    forged["treatment"]["policy"] = "retuned threshold and ranking rule"
    history = _history_with_parent(parent)

    preflight = evaluate_preflight(
        forged,
        _surfaces(),
        prior_fingerprints=history,
        data_cutoff=DATA_CUTOFF,
        evaluated_at=FREEZE_AT,
        selection_scope_id="scope-" + "2" * 24,
    )

    assert preflight["decision"] == "reject"
    assert "amendment_semantic_change:treatment.policy" in preflight["gates"]["D3"]["reasons"]
    assert "amendment_changed_fields_mismatch" in preflight["gates"]["D3"]["reasons"]

    invalid_attachment = _amended_candidate(parent)
    invalid_attachment["baseline"]["comparator_allocation_attachment_hash"] = "bad"
    invalid = evaluate_preflight(
        invalid_attachment,
        _surfaces(),
        prior_fingerprints=history,
        data_cutoff=DATA_CUTOFF,
        evaluated_at=FREEZE_AT,
        selection_scope_id="scope-" + "2" * 24,
    )
    assert (
        "amendment_attachment_hash_invalid:baseline.comparator_allocation_attachment_hash"
        in invalid["gates"]["D3"]["reasons"]
    )

    phantom = _amended_candidate(parent)
    phantom["baseline"]["comparator_allocation_attachment"] = (
        "data/test/does-not-exist.json"
    )
    phantom["baseline"]["comparator_allocation_attachment_hash"] = "0" * 64
    missing = evaluate_preflight(
        phantom,
        _surfaces(),
        prior_fingerprints=history,
        data_cutoff=DATA_CUTOFF,
        evaluated_at=FREEZE_AT,
        selection_scope_id="scope-" + "2" * 24,
    )
    assert (
        "amendment_attachment_missing:baseline.comparator_allocation_attachment"
        in missing["gates"]["D3"]["reasons"]
    )

    clock_forgery = _amended_candidate(parent)
    clock_forgery["amendment_lineage"]["declared_at"] = (
        "2026-07-20T15:31:00Z"
    )
    clock_result = evaluate_preflight(
        clock_forgery,
        _surfaces(),
        prior_fingerprints=history,
        data_cutoff=DATA_CUTOFF,
        evaluated_at=FREEZE_AT,
        selection_scope_id="scope-" + "2" * 24,
    )
    assert (
        "amendment_declaration_child_clock_mismatch"
        in clock_result["gates"]["D3"]["reasons"]
    )


def _abandoned_ancestor_candidate(parent: dict) -> dict:
    """A never-reserved earlier attempt of the same chain: identical
    fingerprint (so it blocks D3), distinct candidate identity."""

    raw = copy.deepcopy(parent)
    raw["candidate_id"] = "pending"
    raw["created_at"] = "2026-07-20T14:10:00Z"
    raw["next_machine_action"] = "abandoned original pre-mechanism attempt"
    return HypothesisCandidate.with_computed_id(raw).to_dict()


@pytest.fixture
def repo_attestation_dir():
    """Repo-relative scratch dir: attestation artifacts must live in-repo."""

    import shutil
    import uuid

    root = (
        Path(__file__).resolve().parents[1]
        / "data/experiments/exp-20260801-003"
        / f"pytest-{uuid.uuid4().hex[:10]}"
    )
    root.mkdir(parents=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _attestation_artifact(
    directory: Path,
    *,
    original_candidate_id: str | None,
    amended_candidate_id: str,
    child_candidate_id: str | None = None,
    safety_overrides: dict | None = None,
    disposition: str = "parked_pre_reservation",
    record_type: str = "alpha_search_pre_reservation_block",
) -> tuple[str, str]:
    document: dict = {
        "schema_version": 1,
        "record_type": record_type,
        "recorded_at": "2026-07-20T14:58:00Z",
        "amended_candidate_id": amended_candidate_id,
        "safety_state": {
            "candidate_outcomes_accessed": False,
            "experiment_id_reserved": False,
            "experiment_claimed": False,
            "strategy_logic_changed": False,
            "backtest_or_replay_run": False,
            "orders_changed": False,
            "trade_enabled": False,
            **(safety_overrides or {}),
        },
        "disposition": disposition,
    }
    if original_candidate_id is not None:
        document["original_candidate_id"] = original_candidate_id
    if child_candidate_id is not None:
        document["reusable_artifacts"] = {"child_candidate_id": child_candidate_id}
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "pre_reservation_block.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[1]
    locator = path.relative_to(repo_root).as_posix()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return locator, digest


def _attested_candidate(
    parent: dict,
    locator: str,
    digest: str,
    *,
    ancestor_id: str,
) -> dict:
    candidate = _amended_candidate(parent)
    raw = copy.deepcopy(candidate)
    raw["candidate_id"] = "pending"
    raw["amendment_lineage"]["abandoned_ancestors"] = [
        {
            "ancestor_candidate_id": ancestor_id,
            "attestation_artifact": locator,
            "attestation_artifact_hash": digest,
        }
    ]
    return HypothesisCandidate.with_computed_id(raw).to_dict()


def _abandoned_ancestor_preflight(candidate: dict, history: dict) -> dict:
    return evaluate_preflight(
        candidate,
        _surfaces(),
        prior_fingerprints=history,
        data_cutoff=DATA_CUTOFF,
        evaluated_at=FREEZE_AT,
        selection_scope_id="scope-" + "2" * 24,
    )


def test_two_record_abort_chain_blocks_without_attestation(
    trusted_lineage_history: None,
) -> None:
    parent = _lineage_parent()
    ancestor = _abandoned_ancestor_candidate(parent)
    candidate = _amended_candidate(parent)
    history = _history_with_parent(parent, abandoned_candidate=ancestor)

    preflight = _abandoned_ancestor_preflight(candidate, history)

    assert preflight["decision"] == "reject"
    assert preflight["gates"]["D3"]["reasons"]


def test_attested_abandoned_ancestor_waives_recorded_abort_chain(
    trusted_lineage_history: None,
    repo_attestation_dir: Path,
) -> None:
    parent = _lineage_parent()
    ancestor = _abandoned_ancestor_candidate(parent)
    locator, digest = _attestation_artifact(
        repo_attestation_dir,
        original_candidate_id=ancestor["candidate_id"],
        amended_candidate_id=parent["candidate_id"],
    )
    candidate = _attested_candidate(
        parent, locator, digest, ancestor_id=ancestor["candidate_id"]
    )
    history = _history_with_parent(parent, abandoned_candidate=ancestor)
    surfaces = _surfaces()
    manifest = _manifest(surfaces, prior_fingerprints=history)

    panel = freeze_selection_panel(
        [candidate],
        surfaces,
        scope_manifest=manifest,
        selection_pool_complete=True,
        prior_fingerprints=history,
    )

    preflight = panel["preflight_decisions"][candidate["candidate_id"]]
    assert preflight["decision"] == "pass"
    assert preflight["gates"]["D3"] == {"status": "pass", "reasons": []}
    assert panel["selected_candidate_id"] == candidate["candidate_id"]
    assert _strict_verify(panel, surfaces, manifest, history)["valid"] is True


def test_abandoned_ancestor_missing_artifact_fails_closed(
    trusted_lineage_history: None,
) -> None:
    parent = _lineage_parent()
    ancestor = _abandoned_ancestor_candidate(parent)
    candidate = _attested_candidate(
        parent,
        "data/test/does-not-exist-attestation.json",
        "0" * 64,
        ancestor_id=ancestor["candidate_id"],
    )
    history = _history_with_parent(parent, abandoned_candidate=ancestor)

    preflight = _abandoned_ancestor_preflight(candidate, history)

    assert preflight["decision"] == "reject"
    assert (
        f"abandoned_ancestor_artifact_missing:{ancestor['candidate_id']}"
        in preflight["gates"]["D3"]["reasons"]
    )


def test_abandoned_ancestor_hash_mismatch_fails_closed(
    trusted_lineage_history: None,
    repo_attestation_dir: Path,
) -> None:
    parent = _lineage_parent()
    ancestor = _abandoned_ancestor_candidate(parent)
    locator, _ = _attestation_artifact(
        repo_attestation_dir,
        original_candidate_id=ancestor["candidate_id"],
        amended_candidate_id=parent["candidate_id"],
    )
    candidate = _attested_candidate(
        parent, locator, "f" * 64, ancestor_id=ancestor["candidate_id"]
    )
    history = _history_with_parent(parent, abandoned_candidate=ancestor)

    preflight = _abandoned_ancestor_preflight(candidate, history)

    assert preflight["decision"] == "reject"
    assert (
        f"abandoned_ancestor_artifact_hash_mismatch:{ancestor['candidate_id']}"
        in preflight["gates"]["D3"]["reasons"]
    )


def test_abandoned_ancestor_chain_mismatch_fails_closed(
    trusted_lineage_history: None,
    repo_attestation_dir: Path,
) -> None:
    parent = _lineage_parent()
    ancestor = _abandoned_ancestor_candidate(parent)
    locator, digest = _attestation_artifact(
        repo_attestation_dir,
        original_candidate_id=ancestor["candidate_id"],
        amended_candidate_id="cand-" + "9" * 20,
    )
    candidate = _attested_candidate(
        parent, locator, digest, ancestor_id=ancestor["candidate_id"]
    )
    history = _history_with_parent(parent, abandoned_candidate=ancestor)

    preflight = _abandoned_ancestor_preflight(candidate, history)

    assert preflight["decision"] == "reject"
    assert (
        f"abandoned_ancestor_chain_mismatch:{ancestor['candidate_id']}"
        in preflight["gates"]["D3"]["reasons"]
    )


def test_abandoned_ancestor_that_reached_reservation_fails_closed(
    trusted_lineage_history: None,
    repo_attestation_dir: Path,
) -> None:
    parent = _lineage_parent()
    ancestor = _abandoned_ancestor_candidate(parent)
    locator, digest = _attestation_artifact(
        repo_attestation_dir,
        original_candidate_id=ancestor["candidate_id"],
        amended_candidate_id=parent["candidate_id"],
    )
    candidate = _attested_candidate(
        parent, locator, digest, ancestor_id=ancestor["candidate_id"]
    )
    history = _history_with_parent(
        parent,
        abandoned_candidate=ancestor,
        reserved_family_row={
            "family_key": ancestor["candidate_id"],
            "fingerprint": candidate_legacy_fingerprints(parent)[0],
            "representative_exps": ["exp-20260719-002"],
            "status": "single_attempt",
            "reopen_condition": None,
        },
    )

    preflight = _abandoned_ancestor_preflight(candidate, history)

    assert preflight["decision"] == "reject"
    assert (
        f"abandoned_ancestor_non_discovery_record:{ancestor['candidate_id']}"
        in preflight["gates"]["D3"]["reasons"]
    )

    reserved_locator, reserved_digest = _attestation_artifact(
        repo_attestation_dir / f"reserved-{ancestor['candidate_id'][-6:]}",
        original_candidate_id=ancestor["candidate_id"],
        amended_candidate_id=parent["candidate_id"],
        safety_overrides={"experiment_id_reserved": True},
    )
    reserved = _attested_candidate(
        parent,
        reserved_locator,
        reserved_digest,
        ancestor_id=ancestor["candidate_id"],
    )
    clean_history = _history_with_parent(parent, abandoned_candidate=ancestor)

    reserved_preflight = _abandoned_ancestor_preflight(reserved, clean_history)

    assert reserved_preflight["decision"] == "reject"
    assert (
        f"abandoned_ancestor_reached_reservation:{ancestor['candidate_id']}"
        in reserved_preflight["gates"]["D3"]["reasons"]
    )


def test_abandoned_ancestor_outcome_bearing_artifact_fails_closed(
    trusted_lineage_history: None,
    repo_attestation_dir: Path,
) -> None:
    parent = _lineage_parent()
    ancestor = _abandoned_ancestor_candidate(parent)
    locator, digest = _attestation_artifact(
        repo_attestation_dir,
        original_candidate_id=ancestor["candidate_id"],
        amended_candidate_id=parent["candidate_id"],
        safety_overrides={"candidate_outcomes_accessed": True},
    )
    candidate = _attested_candidate(
        parent, locator, digest, ancestor_id=ancestor["candidate_id"]
    )
    history = _history_with_parent(parent, abandoned_candidate=ancestor)

    preflight = _abandoned_ancestor_preflight(candidate, history)

    assert preflight["decision"] == "reject"
    assert (
        f"abandoned_ancestor_artifact_not_outcome_blind:{ancestor['candidate_id']}"
        in preflight["gates"]["D3"]["reasons"]
    )


def test_abandoned_ancestor_does_not_waive_unrelated_neighbor(
    trusted_lineage_history: None,
    repo_attestation_dir: Path,
) -> None:
    parent = _lineage_parent()
    ancestor = _abandoned_ancestor_candidate(parent)
    locator, digest = _attestation_artifact(
        repo_attestation_dir,
        original_candidate_id=ancestor["candidate_id"],
        amended_candidate_id=parent["candidate_id"],
    )
    candidate = _attested_candidate(
        parent, locator, digest, ancestor_id=ancestor["candidate_id"]
    )
    history = _history_with_parent(
        parent, abandoned_candidate=ancestor, include_other_neighbor=True
    )

    preflight = _abandoned_ancestor_preflight(candidate, history)

    assert preflight["decision"] == "reject"
    assert any(
        "exp-20260719-001" in reason
        for reason in preflight["gates"]["D3"]["reasons"]
    )


def test_attested_abandoned_prior_child_clears_competing_veto(
    trusted_lineage_history: None,
    repo_attestation_dir: Path,
) -> None:
    parent = _lineage_parent()
    prior_child = _amended_candidate(
        parent,
        attachment_suffix="abandoned-prior-child",
        declared_at="2026-07-20T14:50:00Z",
    )
    locator, digest = _attestation_artifact(
        repo_attestation_dir,
        original_candidate_id=None,
        amended_candidate_id=parent["candidate_id"],
        child_candidate_id=prior_child["candidate_id"],
    )
    candidate = _attested_candidate(
        parent, locator, digest, ancestor_id=prior_child["candidate_id"]
    )
    history = _history_with_parent(parent, competing_child=prior_child)

    preflight = _abandoned_ancestor_preflight(candidate, history)

    assert preflight["decision"] == "pass"
    assert preflight["gates"]["D3"] == {"status": "pass", "reasons": []}


def test_abandoned_prior_child_without_recorded_parent_link_stays_blocked(
    trusted_lineage_history: None,
    repo_attestation_dir: Path,
) -> None:
    parent = _lineage_parent()
    unlinked_prior = _abandoned_ancestor_candidate(parent)
    locator, digest = _attestation_artifact(
        repo_attestation_dir,
        original_candidate_id=None,
        amended_candidate_id=parent["candidate_id"],
        child_candidate_id=unlinked_prior["candidate_id"],
    )
    candidate = _attested_candidate(
        parent, locator, digest, ancestor_id=unlinked_prior["candidate_id"]
    )
    history = _history_with_parent(parent, abandoned_candidate=unlinked_prior)

    preflight = _abandoned_ancestor_preflight(candidate, history)

    assert preflight["decision"] == "reject"
    assert (
        f"abandoned_ancestor_chain_mismatch:{unlinked_prior['candidate_id']}"
        in preflight["gates"]["D3"]["reasons"]
    )


def test_amendment_rejects_hash_bound_outcome_bearing_attachment_content(
    trusted_lineage_history: None,
) -> None:
    parent = _lineage_parent()
    forged = _amended_candidate(parent)
    repo_root = Path(__file__).resolve().parents[1]
    outcome_artifact = (
        repo_root
        / "data/backtests/"
        "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
    )
    forged["candidate_id"] = "pending"
    forged["baseline"]["comparator_allocation_attachment"] = (
        outcome_artifact.relative_to(repo_root).as_posix()
    )
    forged["baseline"]["comparator_allocation_attachment_hash"] = hashlib.sha256(
        outcome_artifact.read_bytes()
    ).hexdigest()
    forged = HypothesisCandidate.with_computed_id(forged).to_dict()
    history = _history_with_parent(parent)

    preflight = evaluate_preflight(
        forged,
        _surfaces(),
        prior_fingerprints=history,
        data_cutoff=DATA_CUTOFF,
        evaluated_at=FREEZE_AT,
        selection_scope_id="scope-" + "2" * 24,
    )

    reasons = preflight["gates"]["D3"]["reasons"]
    assert preflight["decision"] == "reject"
    assert preflight["outcome_blind"] is False
    assert "outcome_contamination" in preflight["failure_reasons"]
    assert any(
        reason.startswith(
            "amendment_attachment_content_forbidden_outcome_field:attachment"
        )
        for reason in reasons
    )


def test_amendment_attachment_cutoff_cannot_postdate_preflight_cutoff(
    trusted_lineage_history: None,
) -> None:
    parent = _lineage_parent()
    candidate = _amended_candidate(parent)
    history = _history_with_parent(parent)

    preflight = evaluate_preflight(
        candidate,
        _surfaces(),
        prior_fingerprints=history,
        data_cutoff="2026-07-20T15:14:00Z",
        evaluated_at=FREEZE_AT,
        selection_scope_id="scope-" + "2" * 24,
    )

    assert preflight["decision"] == "reject"
    assert preflight["outcome_blind"] is False
    assert "outcome_contamination" in preflight["failure_reasons"]
    assert (
        "amendment_attachment_content_data_cutoff_after_preflight_cutoff:"
        "baseline.comparator_allocation_attachment"
        in preflight["gates"]["D3"]["reasons"]
    )


def test_amendment_parent_scope_and_panel_tamper_fail_closed(
    trusted_lineage_history: None,
) -> None:
    parent = _lineage_parent()
    wrong_scope = _amended_candidate(
        parent, parent_scope_id="scope-" + "3" * 24
    )
    history = _history_with_parent(parent)
    wrong = evaluate_preflight(
        wrong_scope,
        _surfaces(),
        prior_fingerprints=history,
        data_cutoff=DATA_CUTOFF,
        evaluated_at=FREEZE_AT,
        selection_scope_id="scope-" + "2" * 24,
    )
    assert "amendment_parent_anchor_mismatch" in wrong["gates"]["D3"]["reasons"]

    candidate = _amended_candidate(parent)
    surfaces = _surfaces()
    manifest = _manifest(surfaces, prior_fingerprints=history)
    panel = freeze_selection_panel(
        [candidate],
        surfaces,
        scope_manifest=manifest,
        selection_pool_complete=True,
        prior_fingerprints=history,
    )
    tampered = copy.deepcopy(panel)
    tampered["candidate_snapshots"][0]["amendment_lineage"]["declared_at"] = (
        "2026-07-20T15:31:00Z"
    )
    tampered["candidate_snapshot_hashes"][candidate["candidate_id"]] = stable_hash(
        tampered["candidate_snapshots"][0]
    )
    tampered["panel_hash"] = engine._hash_without_top_level(tampered, "panel_hash")
    with pytest.raises(AlphaSearchError):
        _strict_verify(tampered, surfaces, manifest, history)


def test_amendment_requires_repository_recomputed_history_not_legacy_rows() -> None:
    parent = _lineage_parent()
    candidate = _amended_candidate(parent)
    history = _history_with_parent(parent)
    common = {
        "candidate": candidate,
        "surfaces": _surfaces(),
        "data_cutoff": DATA_CUTOFF,
        "evaluated_at": FREEZE_AT,
        "selection_scope_id": "scope-" + "2" * 24,
    }

    legacy = evaluate_preflight(
        common["candidate"],
        common["surfaces"],
        prior_fingerprints=history["records"],
        data_cutoff=common["data_cutoff"],
        evaluated_at=common["evaluated_at"],
        selection_scope_id=common["selection_scope_id"],
    )
    assert "amendment_repository_history_required" in legacy["gates"]["D3"]["reasons"]

    isolated = evaluate_preflight(
        common["candidate"],
        common["surfaces"],
        prior_fingerprints=history,
        data_cutoff=common["data_cutoff"],
        evaluated_at=common["evaluated_at"],
        selection_scope_id=common["selection_scope_id"],
    )
    assert (
        "amendment_repository_history_unverified"
        in isolated["gates"]["D3"]["reasons"]
    )


def test_new_scope_direct_api_rejects_legacy_bare_prior_list() -> None:
    with pytest.raises(AlphaSearchError, match="historical_snapshot_required"):
        _manifest(_surfaces(), prior_fingerprints=[])


def test_current_muted_revision_candidate_hits_legacy_rejected_family() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    candidate_pool = json.loads(
        (repo_root / "data/alpha_search/phase1_candidate_pool_20260721.json").read_text(
            encoding="utf-8"
        )
    )
    candidate = next(
        row for row in candidate_pool["candidates"] if "unusually muted" in row["hypothesis"]
    )
    surfaces = EvidenceSurfaceRegistry.from_dict(
        json.loads(
            (repo_root / "data/reference/alpha_search_evidence_surfaces.json").read_text(
                encoding="utf-8"
            )
        )
    )
    history = build_historical_prior_snapshot(
        repo_root / "docs/frozen_families.jsonl",
        history_cutoff="2026-07-21T07:59:59Z",
    )
    result = evaluate_preflight(
        candidate,
        surfaces,
        prior_fingerprints=history,
        data_cutoff="2026-07-21T08:01:00Z",
    )
    assert result["gates"]["D3"]["status"] == "reject"
    assert "duplicate_or_frozen" in result["failure_reasons"]
    assert any(
        "exp-20260605-029" in reason for reason in result["gates"]["D3"]["reasons"]
    )


def test_snapshot_cutoff_cannot_postdate_scope_or_preflight(tmp_path: Path) -> None:
    frozen = tmp_path / "frozen.jsonl"
    frozen.write_text(
        json.dumps(
            {
                "family_key": "old_family",
                "fingerprint": {
                    "data_source": "prediction_market",
                    "field_tags": ["old"],
                    "gate_shape": "candidate_pool_top1_10d",
                },
                "representative_exps": ["exp-20260719-001"],
                "status": "single_attempt",
                "reopen_condition": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    future = build_historical_prior_snapshot(
        frozen,
        history_cutoff="2099-01-01T00:00:00Z",
        isolated_fixture=True,
    )
    with pytest.raises(AlphaSearchError, match="historical_snapshot_after_scope_clock"):
        _manifest(_surfaces(), prior_fingerprints=future)
    with pytest.raises(AlphaSearchError, match="historical_snapshot_after_scope_clock"):
        evaluate_preflight(
            _candidate(),
            _surfaces(),
            prior_fingerprints=future,
            data_cutoff=DATA_CUTOFF,
        )


def test_freeze_requires_predeclared_complete_pool_and_batch_policy() -> None:
    surfaces = _surfaces()
    candidates = [
        _candidate("explore", "exploration"),
        _candidate("adjacent", "adjacent"),
        _candidate("exploit", "exploitation"),
    ]
    manifest = _manifest(
        surfaces,
        queue_budgets={"exploration": 1, "adjacent": 1, "exploitation": 1},
        expected_count=3,
        selection_limit=3,
        batch_policy_bundle_id="batch-policy-v1",
    )
    history = copy.deepcopy(TEST_HISTORY_SNAPSHOT)
    panel = freeze_selection_panel(
        candidates,
        surfaces,
        scope_manifest=manifest,
        selection_pool_complete=True,
        prior_fingerprints=history,
    )
    assert _strict_verify(panel, surfaces, manifest, history)["valid"] is True
    assert set(panel["selected_candidate_ids"]) == {
        candidate["candidate_id"] for candidate in candidates
    }

    with pytest.raises(AlphaSearchError, match="incomplete_selection_panel"):
        freeze_selection_panel(
            candidates[:-1],
            surfaces,
            scope_manifest=manifest,
            selection_pool_complete=True,
            prior_fingerprints=history,
        )
    with pytest.raises(AlphaSearchError, match="batch_policy_bundle_id"):
        _manifest(
            surfaces,
            expected_count=3,
            queue_budgets={"exploration": 1, "adjacent": 1, "exploitation": 1},
            selection_limit=3,
        )


def test_external_context_detects_coordinated_preflight_rewrite() -> None:
    panel, surfaces, manifest, priors = _panel()
    candidate_id = panel["candidate_ids"][0]
    tampered = copy.deepcopy(panel)
    tampered["preflight_decisions"][candidate_id]["source_snapshot_hashes"]["market-prior"] = "f" * 64
    tampered["preflight_decisions"][candidate_id]["preflight_hash"] = engine._hash_without_top_level(
        tampered["preflight_decisions"][candidate_id], "preflight_hash"
    )
    tampered["preflight_decision_hashes"][candidate_id] = tampered["preflight_decisions"][candidate_id]["preflight_hash"]
    tampered["panel_hash"] = engine._hash_without_top_level(tampered, "panel_hash")
    with pytest.raises(AlphaSearchError, match="preflight_recomputation_mismatch"):
        _strict_verify(tampered, surfaces, manifest, priors)


def test_no_trade_and_nested_hash_tampering_fail_closed() -> None:
    panel, surfaces, manifest, priors = _panel()
    forged = copy.deepcopy(panel)
    forged["trade_enabled"] = True
    forged["panel_hash"] = engine._hash_without_top_level(forged, "panel_hash")
    with pytest.raises(AlphaSearchError, match="trade_enabled_boundary_violation"):
        _strict_verify(forged, surfaces, manifest, priors)

    changed = _candidate(created_at="2026-07-20T15:31:00Z")
    second = freeze_selection_panel(
        [changed],
        surfaces,
        scope_manifest=manifest,
        selection_pool_complete=True,
        prior_fingerprints=priors,
    )
    assert second["panel_hash"] != panel["panel_hash"]


def test_external_manifest_and_registry_are_required_for_trust_verification() -> None:
    panel, surfaces, manifest, priors = _panel()
    assert verify_selection_panel(panel)["valid"] is True
    with pytest.raises(AlphaSearchError, match="external_scope_manifest_required"):
        verify_selection_panel(panel, require_external_context=True)

    other_manifest = dict(manifest)
    other_manifest["scope_name"] = "forged"
    other_manifest["manifest_hash"] = engine._hash_without_top_level(
        other_manifest, "manifest_hash"
    )
    with pytest.raises(AlphaSearchError, match="external_scope_manifest_mismatch"):
        verify_selection_panel(
            panel,
            surfaces=surfaces,
            scope_manifest=other_manifest,
            prior_fingerprints=priors,
            require_external_context=True,
        )


def test_diversity_selector_covers_three_queues_before_neighbours() -> None:
    candidates = [
        _candidate("explore-high", "exploration"),
        _candidate("explore-low", "exploration"),
        _candidate("adjacent", "adjacent"),
        _candidate("exploit", "exploitation"),
    ]
    preflights = {row["candidate_id"]: {"decision": "pass", "gates": {}} for row in candidates}
    scores = {
        candidates[0]["candidate_id"]: {"total": 1.0},
        candidates[1]["candidate_id"]: {"total": 0.9},
        candidates[2]["candidate_id"]: {"total": 0.7},
        candidates[3]["candidate_id"]: {"total": 0.6},
    }
    selected = select_diverse_candidates(candidates, preflights, scores, limit=3)
    assert set(selected) == {
        candidates[0]["candidate_id"],
        candidates[2]["candidate_id"],
        candidates[3]["candidate_id"],
    }


def test_failure_taxonomy_deduplicates_and_keeps_raw_text() -> None:
    report = build_failure_taxonomy(
        [
            {"experiment_id": "exp-1", "decision": "rejected", "summary": "Signal was already priced in."},
            {"experiment_id": "exp-1", "decision": "duplicate row"},
            {"experiment_id": "exp-2", "primary_failure_reason": "cost_and_carry"},
        ]
    )
    assert report["record_count"] == 2
    assert report["primary_failure_counts"] == {"already_priced": 1, "cost_and_carry": 1}


def test_report_is_read_only_and_uses_strict_verification() -> None:
    panel, surfaces, manifest, priors = _panel()
    report = build_search_report(
        panel,
        surfaces=surfaces,
        scope_manifest=manifest,
        prior_fingerprints=priors,
        require_external_context=True,
    )
    assert report["panel_hash"] == panel["panel_hash"]
    assert report["trade_enabled"] is False
    assert report["experiment_id_reserved"] is False
