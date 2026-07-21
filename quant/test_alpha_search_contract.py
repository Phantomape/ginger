from copy import deepcopy
from dataclasses import replace

import pytest

from quant.alpha_search_contract import (
    ContractValidationError,
    EvidenceSurface,
    ExpectationGap,
    FailureReason,
    HypothesisCandidate,
    PreflightDecision,
    SelectionPanel,
    build_hypothesis_candidate,
    build_selection_panel,
    canonical_hash,
    normalize_evidence_surface,
    research_only_production_impact,
)


def _surface(**overrides):
    row = {
        "surface_id": "prediction_market_event_observer",
        "data_source": "polymarket",
        "component_sources": ["polymarket"],
        "roles": ["independent_evidence", "market_expectation"],
        "artifacts": ["manifest:prediction-market", "ledger:market-shocks"],
        "pit_status": "canonical_pit",
        "evidence_grade": "gate_candidate",
        "settled_count": 12,
        "independent_count": 12,
        "candidate_overlap_count": 4,
        "gate_ready": True,
        "expectation_proxy": {
            "type": "direct_implied_probability",
            "field": "yes_probability",
            "source": "polymarket",
        },
        "source_contract_status": "pass",
        "as_of": "2026-07-20T16:00:00Z",
        "artifact_snapshot_hashes": {
            "manifest:prediction-market": "a" * 64,
            "ledger:market-shocks": "b" * 64,
        },
    }
    row.update(overrides)
    return row


def _gap(**overrides):
    row = {
        "market_prior": {
            "observable": True,
            "proxy_type": "direct_implied_probability",
            "source": "polymarket",
            "known_at": "2026-07-20T12:30:00-04:00",
            "interval": [0.35, 0.39],
            "units": "probability",
        },
        "independent_evidence": [
            {
                "evidence_id": "sec-filing-2",
                "source": "SEC",
                "known_at": "2026-07-20T15:05:00Z",
                "state": "condition_satisfied",
            },
            {
                "evidence_id": "official-release-1",
                "source": "issuer_release",
                "known_at": "2026-07-20T15:00:00Z",
                "state": "milestone_confirmed",
            },
        ],
        "our_posterior": {
            "method": "frozen_calibration_v1",
            "value": 0.56,
            "known_at": "2026-07-20T11:10:00-04:00",
        },
        "gap_definition": "calibrated posterior minus observable market prior",
        "transmission": {
            "affected_tickers": ["AAA"],
            "expected_direction": "long",
            "catalyst": "formal event resolution",
            "half_life": "H5-H20",
        },
    }
    row.update(overrides)
    return row


def _candidate(candidate_id="cand-a", queue="explore", **overrides):
    row = {
        "candidate_id": candidate_id,
        "queue": queue,
        "hypothesis": "Independent facts imply a higher event probability than price.",
        "baseline": "No event-state admission; rank the frozen universe normally.",
        "treatment": "Admit the event-state candidate under the frozen mapping.",
        "horizon": "H5-H20",
        "replacement_comparison": "Cash, SPY, QQQ, and displaced core candidate.",
        "decision_surface": "candidate_pool",
        "mechanism_family": "policy_probability_repricing",
        "fingerprint": {
            "data_source": "polymarket",
            "component_sources": ["polymarket", "sec"],
            "expectation_proxy": "direct_implied_probability",
            "economic_mechanism": "policy_probability_repricing",
            "decision_surface": "candidate_pool",
            "payoff_shape": "long_convex_event_drift",
            "horizon": "H5-H20",
            "execution_dependency": "liquid_cash_equity",
            "portfolio_role": "orthogonal_event_sleeve",
        },
        "surface_ids": ["prediction_market_event_observer", "sec_event_stream"],
        "data_source": "polymarket",
        "component_sources": ["sec", "polymarket"],
        "expectation_gap": _gap(),
        "why_not_arbitraged": "Issuer mapping and event semantics are costly to maintain.",
        "falsifier": "No repricing after confirmed independent evidence within H20.",
        "evidence_grade": "gate_candidate",
        "source_readiness_snapshot": [
            {
                "surface_id": "prediction_market_event_observer",
                "snapshot_hash": "f" * 64,
            },
            {"surface_id": "sec_event_stream", "snapshot_hash": "1" * 64},
        ],
        "next_machine_action": "Run outcome-blind D0-D3 preflight.",
        "execution": {
            "instrument": "cash_equity",
            "liquidity_dependency": "minimum decision-time ADV",
            "trade_enabled": False,
        },
        "portfolio_role": "orthogonal_event_sleeve",
        "production_impact": {"trade_enabled": False, "orders_changed": False},
    }
    row.update(overrides)
    return row


def _assert_code(code, func):
    with pytest.raises(ContractValidationError) as caught:
        func()
    assert caught.value.code == code
    assert caught.value.to_dict()["code"] == code


def _preflight(candidate_id="cand-a", *, decision="pass", scope_id="scope-test"):
    failed = decision != "pass"
    row = {
        "schema_version": 1,
        "record_type": "preflight_decision",
        "candidate_id": candidate_id,
        "selection_scope_id": scope_id,
        "evaluated_at": "2026-07-20T16:00:00Z",
        "preflight_version": "preflight-v1",
        "data_cutoff": "2026-07-20",
        "outcome_blind": True,
        "outcome_fields_excluded": ["pnl", "realized_return"],
        "source_snapshot_hashes": {"surface-a": "c" * 64},
        "declared_evidence_grade": "lead" if failed else "gate_candidate",
        "maximum_supported_evidence_grade": "lead" if failed else "gate_candidate",
        "fingerprint_hash": "d" * 64,
        "gates": {
            "D0": {
                "status": "park" if failed else "pass",
                "reasons": ["source_not_ready"] if failed else [],
            },
            "D1": {"status": "pass", "reasons": []},
            "D2": {"status": "pass", "reasons": []},
            "D3": {"status": "pass", "reasons": []},
        },
        "decision": decision,
        "failure_reasons": ["pit_or_source_failure"] if failed else [],
        "reopen_condition": {"independent_count_gte": 20} if failed else None,
        "trade_enabled": False,
        "production_impact": research_only_production_impact(),
    }
    semantic = deepcopy(row)
    row["preflight_hash"] = canonical_hash(semantic)
    return row


def _scope_manifest(queue_budgets):
    row = {
        "schema_version": 1,
        "manifest_version": "alpha_search_scope_manifest_v1",
        "scope_name": "contract-test-scope",
        "preregistered_at": "2026-07-20T14:00:00Z",
        "data_cutoff": "2026-07-20T16:00:00Z",
        "freeze_at": "2026-07-20T17:00:00Z",
        "generator_version": "test-generator-v1",
        "candidate_generation_config": {"mode": "fixed-fixture"},
        "allowed_surface_ids": [
            "prediction_market_event_observer",
            "sec_event_stream",
        ],
        "surface_registry_hash": "e" * 64,
        "prior_fingerprint_snapshot_hash": canonical_hash([]),
        "prior_fingerprint_count": 0,
        "selector_version": "contract-compatibility-v1",
        "score_version": "contract-unscored-v1",
        "queue_budgets": queue_budgets,
        "expected_candidate_count": sum(queue_budgets.values()),
        "selection_limit": 1,
        "batch_policy_bundle_id": None,
        "outcome_blind": True,
        "trade_enabled": False,
    }
    row["manifest_hash"] = canonical_hash(row)
    return row


def _build_panel(candidates):
    rows = [
        row
        if isinstance(row, HypothesisCandidate)
        else build_hypothesis_candidate(row)
        for row in candidates
    ]
    aliases = {"explore": "exploration", "exploit": "exploitation"}
    budgets = {"exploration": 0, "adjacent": 0, "exploitation": 0}
    for row in rows:
        queue = row.search_queue if isinstance(row, HypothesisCandidate) else row.get(
            "search_queue", row.get("queue")
        )
        budgets[aliases.get(queue, queue)] += 1
    return build_selection_panel(rows, scope_manifest=_scope_manifest(budgets))


def test_evidence_surface_round_trip_normalises_sets_and_has_stable_hash():
    first = EvidenceSurface.from_dict(
        _surface(
            component_sources=["polymarket", "polymarket"],
            roles=["market_expectation", "independent_evidence"],
            artifacts=["ledger:market-shocks", "manifest:prediction-market"],
        )
    )
    second_raw = dict(reversed(list(_surface().items())))
    second = EvidenceSurface.from_dict(second_raw)

    assert first.component_sources == ("polymarket",)
    assert first.roles == ("independent_evidence", "market_expectation")
    assert first.to_dict() == second.to_dict()
    assert first.canonical_hash == second.canonical_hash
    assert normalize_evidence_surface(first) == first.to_dict()


def test_non_market_surface_may_omit_proxy_but_market_surface_may_not():
    independent = EvidenceSurface.from_dict(
        _surface(
            roles=["independent_evidence"],
            expectation_proxy=None,
        )
    )
    assert independent.expectation_proxy is None

    _assert_code(
        "expectation_proxy_required",
        lambda: EvidenceSurface.from_dict(_surface(expectation_proxy=None)),
    )


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"pit_status": "future_leaky"}, "invalid_pit_status"),
        ({"evidence_grade": "observer"}, "gate_readiness_mismatch"),
        ({"gate_ready": False}, "gate_readiness_mismatch"),
        ({"settled_count": 0}, "settled_count_required"),
        ({"settled_count": True}, "nonnegative_integer_required"),
    ],
)
def test_evidence_surface_pit_and_readiness_fail_closed(changes, code):
    _assert_code(code, lambda: EvidenceSurface.from_dict(_surface(**changes)))


def test_canonical_pit_does_not_claim_sample_maturity_by_itself():
    surface = EvidenceSurface.from_dict(
        _surface(
            evidence_grade="observer",
            settled_count=0,
            independent_count=3,
            candidate_overlap_count=0,
            gate_ready=False,
            source_contract_status="partial",
            as_of=None,
            artifact_snapshot_hashes={},
        )
    )
    assert surface.pit_status == "canonical_pit"
    assert surface.evidence_grade == "observer"
    assert surface.gate_ready is False


def test_gate_ready_surface_hashes_exact_registered_artifacts():
    _assert_code(
        "artifact_snapshot_binding_mismatch",
        lambda: EvidenceSurface.from_dict(
            _surface(artifact_snapshot_hashes={"unregistered:artifact": "a" * 64})
        ),
    )
    missing_status = _surface()
    del missing_status["source_contract_status"]
    _assert_code(
        "source_contract_status_required",
        lambda: EvidenceSurface.from_dict(missing_status),
    )


def test_evidence_surface_exposes_independent_overlap_and_park_contract():
    parked = EvidenceSurface.from_dict(
        _surface(
            pit_status="pit_forward_unsettled",
            evidence_grade="observer",
            settled_count=2,
            gate_ready=False,
            independent_count=8,
            candidate_overlap_count=3,
            saturation_status="parked",
            reopen_condition={"independent_count_gte": 20},
            source_contract_status="partial",
        )
    )
    assert parked.independent_count == 8
    assert parked.candidate_overlap_count == 3
    assert parked.to_dict()["reopen_condition"] == {"independent_count_gte": 20}

    _assert_code(
        "reopen_condition_required",
        lambda: EvidenceSurface.from_dict(
            _surface(
                pit_status="pit_forward_unsettled",
                evidence_grade="observer",
                gate_ready=False,
                saturation_status="parked",
            )
        ),
    )


def test_expectation_gap_requires_observable_market_prior_and_pit_evidence():
    gap = ExpectationGap.from_dict(_gap())

    assert gap.market_prior["known_at"] == "2026-07-20T16:30:00Z"
    assert gap.our_posterior["known_at"] == "2026-07-20T15:10:00Z"
    assert gap.to_dict()["market_prior"]["interval"] == [0.35, 0.39]

    unobservable = _gap()
    unobservable["market_prior"]["observable"] = False
    _assert_code(
        "market_prior_not_observable",
        lambda: ExpectationGap.from_dict(unobservable),
    )

    missing_clock = _gap()
    del missing_clock["independent_evidence"][0]["known_at"]
    _assert_code("missing_field", lambda: ExpectationGap.from_dict(missing_clock))


def test_expectation_gap_hash_is_independent_of_evidence_input_order():
    first = ExpectationGap.from_dict(_gap())
    reverse = _gap()
    reverse["independent_evidence"].reverse()
    second = ExpectationGap.from_dict(reverse)

    assert first.to_dict() == second.to_dict()
    assert first.canonical_hash == second.canonical_hash


@pytest.mark.parametrize(
    "mutation,code",
    [
        (
            lambda row: row["market_prior"].update({"interval": [0.6, 0.2]}),
            "invalid_interval",
        ),
        (
            lambda row: row["market_prior"].update({"known_at": "2026-07-20T12:00:00"}),
            "invalid_known_at",
        ),
        (
            lambda row: row["independent_evidence"][0].update({"realized_return": 0.2}),
            "forbidden_outcome_field",
        ),
    ],
)
def test_expectation_gap_rejects_bad_chronology_or_outcome_injection(mutation, code):
    row = _gap()
    mutation(row)
    _assert_code(code, lambda: ExpectationGap.from_dict(row))


def test_candidate_accepts_short_queue_aliases_and_emits_canonical_names():
    exploration = HypothesisCandidate.from_dict(_candidate(queue=" EXPLORE "))
    exploitation = HypothesisCandidate.from_dict(_candidate(queue="exploit"))
    adjacent = HypothesisCandidate.from_dict(_candidate(queue="adjacent"))

    assert exploration.queue == "exploration"
    assert exploitation.queue == "exploitation"
    assert adjacent.queue == "adjacent"
    assert exploration.to_dict()["search_queue"] == "exploration"
    assert all(value is False for value in exploration.production_impact.values())
    assert set(research_only_production_impact()).issubset(exploration.production_impact)


def test_document_v1_candidate_is_accepted_and_emits_nested_canonical_contract():
    document = {
        "schema_version": 1,
        "candidate_id": "cand-document",
        "search_queue": "exploration",
        "title": "Observable prior versus filing evidence",
        "hypothesis": "A filed fact changes probability before equity reprices.",
        "fingerprint": {
            "data_source": "prediction_market",
            "component_sources": ["prediction_market", "official_filings"],
            "expectation_proxy": "direct_implied_probability",
            "economic_mechanism": "policy_probability_repricing",
            "decision_surface": "candidate_pool",
            "payoff_shape": "event_drift",
            "horizon": "H5_H20",
            "execution_dependency": "liquid_cash_equity",
            "portfolio_role": "orthogonal_event_sleeve",
        },
        "surface_ids": ["market-prior", "independent-fact"],
        "market_prior": {
            "proxy_type": "direct_implied",
            "surface_id": "market-prior",
            "as_of": "2026-07-20T14:00:00Z",
            "value": 0.42,
            "unit": "probability",
            "observability_grade": "direct",
        },
        "independent_evidence": [
            {
                "evidence_id": "fact-1",
                "surface_id": "independent-fact",
                "known_at": "2026-07-20T13:55:00Z",
                "independence_from_prior": "pass",
            }
        ],
        "our_posterior": {
            "value": 0.61,
            "method": "frozen_calibrator_v1",
            "as_of": "2026-07-20T14:00:00Z",
        },
        "expectation_gap": {"signed_value": 0.19, "unit": "probability_points"},
        "transmission": {
            "affected_tickers": ["AAA"],
            "expected_direction": "positive",
            "catalyst": "formal decision",
            "half_life": "10 sessions",
        },
        "why_not_arbitraged": "Cross-source mapping is costly.",
        "falsifier": "No repricing after timestamp-safe alignment.",
        "baseline": {"universe": ["AAA"], "policy": "cash"},
        "treatment": {"policy": "frozen event rule"},
        "replacement_value_comparator": "cash/SPY/QQQ/core",
        "expected_horizon": "H5_H20",
        "execution_envelope": {
            "intended_instrument": "cash equity",
            "liquidity_dependency": "ADV floor",
            "costs_and_carry": "fixed bps model",
            "borrow_dependency": "none",
            "capacity_constraint": "paper cap",
            "timing_constraint": "next session open",
        },
        "evidence_grade": "gate_candidate",
        "source_readiness_snapshot": [
            {"surface_id": "market-prior", "snapshot_hash": "2" * 64},
            {"surface_id": "independent-fact", "snapshot_hash": "3" * 64},
        ],
    }
    candidate = HypothesisCandidate.from_dict(document)
    canonical = candidate.to_dict()

    assert candidate.queue == "exploration"
    assert canonical["search_queue"] == "exploration"
    assert "market_prior" not in canonical
    assert canonical["expectation_gap"]["market_prior"]["observable"] is True
    assert canonical["expectation_gap"]["gap"]["signed_value"] == 0.19
    assert canonical["baseline"] == {"policy": "cash", "universe": ["AAA"]}
    assert all(value is False for value in canonical["production_impact"].values())


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("queue", "random", "invalid_queue"),
        ("hypothesis", " ", "empty_string"),
        ("baseline", "", "empty_string"),
        ("treatment", "", "empty_string"),
        ("horizon", "", "empty_string"),
        ("replacement_comparison", "", "empty_string"),
        ("falsifier", "", "empty_string"),
        ("component_sources", [], "nonempty_list_required"),
        ("surface_ids", [], "nonempty_list_required"),
        ("execution", {}, "nonempty_mapping_required"),
    ],
)
def test_candidate_required_contract_fields_fail_closed(field, value, code):
    _assert_code(
        code,
        lambda: HypothesisCandidate.from_dict(_candidate(**{field: value})),
    )


def test_candidate_requires_all_false_production_and_research_execution():
    _assert_code(
        "production_impact_not_false",
        lambda: HypothesisCandidate.from_dict(
            _candidate(production_impact={"trade_enabled": True})
        ),
    )
    _assert_code(
        "boolean_required",
        lambda: HypothesisCandidate.from_dict(
            _candidate(production_impact={"trade_enabled": 0})
        ),
    )
    _assert_code(
        "research_execution_not_false",
        lambda: HypothesisCandidate.from_dict(
            _candidate(execution={"instrument": "cash_equity", "live_ready": True})
        ),
    )


def test_candidate_requires_complete_consistent_structured_fingerprint():
    missing = _candidate()
    del missing["fingerprint"]["payoff_shape"]
    _assert_code("missing_field", lambda: HypothesisCandidate.from_dict(missing))

    mismatch = _candidate()
    mismatch["fingerprint"]["component_sources"] = ["polymarket"]
    _assert_code(
        "fingerprint_mismatch",
        lambda: HypothesisCandidate.from_dict(mismatch),
    )

    prior_mismatch = _candidate()
    prior_mismatch["fingerprint"]["expectation_proxy"] = "explicit_consensus"
    _assert_code(
        "fingerprint_mismatch",
        lambda: HypothesisCandidate.from_dict(prior_mismatch),
    )


def test_candidate_rejects_outcome_fields_at_any_depth_before_unknown_fields():
    top_level = _candidate()
    top_level["pnl"] = 123
    _assert_code(
        "forbidden_outcome_field",
        lambda: HypothesisCandidate.from_dict(top_level),
    )

    nested = _candidate()
    nested["execution"]["after_metrics"] = {"sharpe": 2.0}
    _assert_code(
        "forbidden_outcome_field",
        lambda: HypothesisCandidate.from_dict(nested),
    )


def test_candidate_instance_replace_cannot_bypass_outcome_or_prediction_schema():
    candidate = HypothesisCandidate.from_dict(_candidate())
    _assert_code(
        "forbidden_outcome_field",
        lambda: replace(candidate, prediction={"post_event_return": 0.25}),
    )
    _assert_code(
        "unknown_field",
        lambda: replace(
            candidate,
            prediction={
                "success_probability": 0.4,
                "main_failure_modes": ["already priced"],
                "confidence_reason": "Sparse calibration sample.",
                "position_size": 1.0,
            },
        ),
    )


def test_plain_event_lead_abstains_from_market_expectation_claim():
    document = HypothesisCandidate.from_dict(_candidate()).to_dict()
    document["candidate_kind"] = "plain_event_lead"
    document["expectation_gap"] = None
    document["fingerprint"]["expectation_proxy"] = "unidentified"
    document["evidence_grade"] = "lead"
    lead = HypothesisCandidate.with_computed_id(document)

    assert lead.candidate_kind == "plain_event_lead"
    assert lead.expectation_gap is None
    assert lead.evidence_grade == "lead"

    upgraded = deepcopy(document)
    upgraded["evidence_grade"] = "observer"
    _assert_code(
        "plain_event_grade_mismatch",
        lambda: HypothesisCandidate.from_dict(upgraded),
    )

    panel = _build_panel([lead])
    preflight = panel.preflight_decisions[lead.candidate_id]
    assert preflight.decision == "park"
    assert preflight.gates["D1"]["status"] == "park"
    assert FailureReason.MARKET_EXPECTATION_UNIDENTIFIED in preflight.failure_reasons


def test_early_expectation_gap_lead_may_abstain_from_ticker_mapping():
    row = _candidate(evidence_grade="lead")
    row["expectation_gap"]["transmission"]["affected_tickers"] = []
    assert HypothesisCandidate.from_dict(row).catalyst == "formal event resolution"

    row["evidence_grade"] = "observed_only"
    _assert_code(
        "affected_tickers_required",
        lambda: HypothesisCandidate.from_dict(row),
    )


def test_panel_identity_is_order_independent_and_commits_complete_candidates():
    first = _candidate("cand-a", "explore")
    second = _candidate(
        "cand-b",
        "exploit",
        why_not_arbitraged="A different fixed constraint explains delayed repricing.",
    )

    panel_ab = _build_panel([first, second])
    panel_ba = _build_panel([second, first])

    assert panel_ab.panel_hash == panel_ba.panel_hash
    assert panel_ab.selection_scope_id == panel_ba.selection_scope_id
    assert panel_ab.to_dict() == panel_ba.to_dict()
    assert panel_ab.to_dict()["candidate_ids"] == sorted(
        panel_ab.to_dict()["candidate_ids"]
    )
    assert all(value.startswith("cand-") for value in panel_ab.candidate_ids)

    changed = deepcopy(second)
    changed["falsifier"] = "A materially different frozen falsifier."
    changed_panel = _build_panel([first, changed])
    assert changed_panel.panel_hash != panel_ab.panel_hash
    assert changed_panel.selection_scope_id == panel_ab.selection_scope_id


def test_semantic_candidate_id_excludes_id_authorship_and_blocks_alias_duplicates():
    canonical = HypothesisCandidate.from_dict(_candidate()).to_dict()
    canonical["created_at"] = "2026-07-20T12:00:00Z"
    canonical["created_by"] = "consensus-agent"
    first = HypothesisCandidate.with_computed_id(canonical)
    assert first.has_semantic_candidate_id is True
    assert first.validate_semantic_id() is first

    same_semantics = first.to_dict()
    same_semantics["candidate_id"] = "cand-arbitrary-alias"
    same_semantics["created_at"] = "2026-07-21T12:00:00Z"
    same_semantics["created_by"] = "contrarian-agent"
    second = HypothesisCandidate.from_dict(same_semantics)
    assert second.semantic_hash == first.semantic_hash
    _assert_code(
        "candidate_id_mismatch",
        lambda: second.validate_semantic_id(),
    )
    _assert_code(
        "candidate_id_mismatch",
        lambda: _build_panel([first, second]),
    )


def test_readiness_refresh_keeps_candidate_identity_but_changes_frozen_snapshot_hash():
    first = HypothesisCandidate.with_computed_id(_candidate())
    refreshed_document = first.to_dict()
    refreshed_document["source_readiness_snapshot"][0]["snapshot_hash"] = "9" * 64
    refreshed = HypothesisCandidate.from_dict(refreshed_document)

    assert refreshed.expected_candidate_id == first.expected_candidate_id
    assert refreshed.semantic_hash == first.semantic_hash
    assert refreshed.canonical_hash != first.canonical_hash

    manifest = _scope_manifest(
        {"exploration": 1, "adjacent": 0, "exploitation": 0}
    )
    first_panel = build_selection_panel([first], scope_manifest=manifest)
    refreshed_panel = build_selection_panel([refreshed], scope_manifest=manifest)
    candidate_id = first.candidate_id
    assert (
        first_panel.candidate_snapshot_hashes[candidate_id]
        != refreshed_panel.candidate_snapshot_hashes[candidate_id]
    )
    assert first_panel.panel_hash != refreshed_panel.panel_hash


def test_panel_rejects_empty_duplicates_and_claimed_hash_tampering():
    _assert_code(
        "empty_panel",
        lambda: build_selection_panel(
            [],
            scope_manifest=_scope_manifest(
                {"exploration": 1, "adjacent": 0, "exploitation": 0}
            ),
        ),
    )
    _assert_code(
        "duplicate_candidate_id",
        lambda: _build_panel([_candidate(), _candidate()]),
    )

    panel = _build_panel([_candidate()]).to_dict()
    panel["panel_hash"] = "0" * 64
    _assert_code("panel_hash_mismatch", lambda: SelectionPanel.from_dict(panel))


def test_panel_binds_preregistered_manifest_and_every_preflight_scope():
    panel = _build_panel([_candidate()]).to_dict()

    manifest_tamper = deepcopy(panel)
    manifest_tamper["scope_manifest"]["candidate_generation_config"]["mode"] = "post-hoc"
    _assert_code(
        "scope_manifest_hash_mismatch",
        lambda: SelectionPanel.from_dict(manifest_tamper),
    )

    empty_history_tamper = _scope_manifest(
        {"exploration": 1, "adjacent": 0, "exploitation": 0}
    )
    empty_history_tamper["prior_fingerprint_snapshot_hash"] = "4" * 64
    unhashed_manifest = deepcopy(empty_history_tamper)
    unhashed_manifest.pop("manifest_hash")
    empty_history_tamper["manifest_hash"] = canonical_hash(unhashed_manifest)
    _assert_code(
        "prior_fingerprint_snapshot_mismatch",
        lambda: build_selection_panel(
            [_candidate()], scope_manifest=empty_history_tamper
        ),
    )

    scope_tamper = deepcopy(panel)
    candidate_id = scope_tamper["candidate_ids"][0]
    preflight = scope_tamper["preflight_decisions"][candidate_id]
    preflight["selection_scope_id"] = "scope-forged"
    unhashed_preflight = deepcopy(preflight)
    unhashed_preflight.pop("preflight_hash")
    preflight["preflight_hash"] = canonical_hash(unhashed_preflight)
    scope_tamper["preflight_decision_hashes"][candidate_id] = preflight[
        "preflight_hash"
    ]
    unhashed_panel = deepcopy(scope_tamper)
    unhashed_panel.pop("panel_hash")
    scope_tamper["panel_hash"] = canonical_hash(unhashed_panel)
    _assert_code(
        "preflight_scope_mismatch",
        lambda: SelectionPanel.from_dict(scope_tamper),
    )


def test_preflight_decision_uses_closed_failure_taxonomy_and_reduces_d0_d3():
    passed = PreflightDecision.from_dict(_preflight())
    assert passed.evaluated_at == "2026-07-20T16:00:00Z"
    assert passed.decision == "pass"

    failed = PreflightDecision.from_dict(
        _preflight("cand-b", decision="park")
    )
    assert failed.failure_reasons == (FailureReason.PIT_OR_SOURCE_FAILURE,)

    invalid = failed.to_dict()
    invalid["failure_reasons"] = ["invented_reason"]
    _assert_code(
        "invalid_failure_reason", lambda: PreflightDecision.from_dict(invalid)
    )

    wrong_reduction = _preflight(decision="park")
    wrong_reduction["decision"] = "reject"
    wrong_reduction["preflight_hash"] = "0" * 64
    _assert_code(
        "preflight_decision_mismatch",
        lambda: PreflightDecision.from_dict(wrong_reduction),
    )

    unsupported_pass = _preflight()
    unsupported_pass["maximum_supported_evidence_grade"] = "lead"
    unhashed = deepcopy(unsupported_pass)
    unhashed.pop("preflight_hash")
    unsupported_pass["preflight_hash"] = canonical_hash(unhashed)
    _assert_code(
        "preflight_grade_mismatch",
        lambda: PreflightDecision.from_dict(unsupported_pass),
    )


def test_failure_reason_enum_matches_architecture_closed_set():
    assert {reason.value for reason in FailureReason} == {
        "no_gross_edge",
        "already_priced",
        "wrong_transmission_mapping",
        "no_candidate_overlap",
        "market_expectation_unidentified",
        "pit_or_source_failure",
        "cost_and_carry",
        "borrow_or_capacity",
        "core_opportunity_cost",
        "concentration",
        "tail_risk",
        "insufficient_independent_rows",
        "duplicate_or_frozen",
        "incomplete_selection_panel",
        "outcome_contamination",
        "unclassified",
    }


def test_canonical_hash_rejects_nonfinite_numbers():
    _assert_code("invalid_json_value", lambda: canonical_hash({"value": float("nan")}))
