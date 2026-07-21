from __future__ import annotations

import copy

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


PREREGISTERED_AT = "2026-07-20T15:00:00Z"
DATA_CUTOFF = "2026-07-20T15:15:00Z"
CREATED_AT = "2026-07-20T15:30:00Z"
FREEZE_AT = "2026-07-20T16:00:00Z"


def _surface(
    surface_id: str,
    source: str,
    *,
    roles: list[str],
    proxy_type: str | None = None,
    grade: str = "gate_candidate",
    saturation: str = "open",
    source_status: str = "pass",
    as_of: str = "2026-07-20T14:00:00Z",
) -> dict:
    artifact = f"data/test/{surface_id}.json"
    gate_ready = grade == "gate_candidate"
    pit_status = {
        "lead": "snapshot_only",
        "observer": "pit_forward_unsettled",
        "observed_only": "settled_forward_sufficient",
        "gate_candidate": "canonical_pit",
    }[grade]
    return {
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


def _surfaces(*, prior_grade: str = "gate_candidate") -> EvidenceSurfaceRegistry:
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


def _manifest(
    surfaces: EvidenceSurfaceRegistry,
    *,
    queue_budgets: dict[str, int] | None = None,
    expected_count: int = 1,
    selection_limit: int = 1,
    batch_policy_bundle_id: str | None = None,
    prior_fingerprints: list = None,
) -> dict:
    prior_fingerprints = [] if prior_fingerprints is None else prior_fingerprints
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
    prior_fingerprints: list | None = None,
) -> tuple[dict, EvidenceSurfaceRegistry, dict, list]:
    candidates = [_candidate()] if candidates is None else candidates
    surfaces = _surfaces() if surfaces is None else surfaces
    prior_fingerprints = [] if prior_fingerprints is None else prior_fingerprints
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
        "prior_fingerprints": [],
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
            prior_fingerprints=[],
        )


def test_unrelated_gate_surface_cannot_upgrade_weak_actual_prior() -> None:
    surfaces = _surfaces(prior_grade="observer")
    candidate = _candidate(grade="observed_only")
    result = evaluate_preflight(candidate, surfaces, data_cutoff=DATA_CUTOFF)
    assert result["decision"] == "park"
    assert result["maximum_supported_evidence_grade"] == "observer"
    assert "insufficient_independent_rows" in result["failure_reasons"]


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
    fingerprint_hash = evaluate_preflight(
        candidate, _surfaces(), data_cutoff=DATA_CUTOFF
    )["fingerprint_hash"]
    surfaces = _surfaces()
    manifest = _manifest(surfaces, prior_fingerprints=[fingerprint_hash])

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
        prior_fingerprints=[fingerprint_hash],
    )
    assert panel["preflight_decisions"][candidate["candidate_id"]]["decision"] == "reject"


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
    panel = freeze_selection_panel(
        candidates,
        surfaces,
        scope_manifest=manifest,
        selection_pool_complete=True,
        prior_fingerprints=[],
    )
    assert _strict_verify(panel, surfaces, manifest, [])["valid"] is True
    assert set(panel["selected_candidate_ids"]) == {
        candidate["candidate_id"] for candidate in candidates
    }

    with pytest.raises(AlphaSearchError, match="incomplete_selection_panel"):
        freeze_selection_panel(
            candidates[:-1],
            surfaces,
            scope_manifest=manifest,
            selection_pool_complete=True,
            prior_fingerprints=[],
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
