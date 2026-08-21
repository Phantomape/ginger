from copy import deepcopy
from dataclasses import replace

import pytest

from quant.test_v2_contracts import (
    _assert_code,
    _evidence,
    _event,
    _mapping,
    _seal_event,
    _source,
)
from quant.v2_contracts import (
    CandidatePool,
    HypothesisCandidate,
    ResearchClaim,
    candidate_entry_input_snapshot_hash,
    candidate_pool_input_snapshot_hash,
    canonical_hash,
    normalize_candidate_pool,
    normalize_hypothesis_candidate,
    normalize_research_claim,
    research_claim_snapshot_hash,
    research_evidence_snapshot_hash,
    universe_event_snapshot_hash,
    universe_input_snapshot_hash,
    validate_candidate_pool,
    validate_candidate_pool_against_inputs,
    validate_evidence_against_source,
    validate_hypothesis_candidate,
    validate_hypothesis_candidate_against_claims,
    validate_research_claim,
    validate_research_claim_against_evidence,
    validate_universe_event_against_evidence,
)


def _seal_claim(row):
    row = deepcopy(row)
    for field in ("evidence_record_ids", "affected_object_ids"):
        row[field] = sorted(row[field])
    row.pop("semantic_hash", None)
    row.pop("record_hash", None)
    semantic = deepcopy(row)
    semantic.pop("recorded_at")
    row["semantic_hash"] = canonical_hash(semantic)
    record = deepcopy(row)
    row["record_hash"] = canonical_hash(record)
    return row


def _claim(*, evidence_records=None, **overrides):
    evidence_records = (
        [_evidence()] if evidence_records is None else list(evidence_records)
    )
    row = {
        "schema_version": 1,
        "record_type": "v2_research_claim",
        "claim_id": "claim-official-event-state-v1",
        "claim_kind": "fact",
        "claim_text": "The official event was confirmed before the decision cutoff.",
        "producer_kind": "ai_skill",
        "producer_id": "research-claim-extractor",
        "producer_version": "1",
        "producer_sha256": "1" * 64,
        "evidence_record_ids": [item["evidence_id"] for item in evidence_records],
        "evidence_snapshot_sha256": research_evidence_snapshot_hash(evidence_records),
        "affected_object_ids": ["sec-aaa"],
        "as_of": "2026-08-20T14:02:00Z",
        "created_at": "2026-08-20T14:04:00Z",
        "known_at": "2026-08-20T14:04:00Z",
        "recorded_at": "2026-08-20T14:05:00Z",
        "pit_tier": "research_pit",
        "known_future_leakage": False,
        "confidence_bps": 8000,
        "confidence_basis": "Direct official evidence with a declared publication clock.",
        "falsifier": "A superseding official revision withdraws confirmation.",
        "next_step": "Test the frozen mechanism without reading outcomes.",
        "outcome_blind": True,
        "authority": "research_only",
        "trade_enabled": False,
    }
    row.update(overrides)
    return _seal_claim(row)


def _policy(policy_id, parameters_sha256):
    return {
        "policy_id": policy_id,
        "entry_policy_version": "entry-v1",
        "ranking_policy_version": "ranking-v1",
        "sizing_policy_version": "sizing-v1",
        "exit_policy_version": "exit-v1",
        "cost_policy_version": "cost-v1",
        "parameters_sha256": parameters_sha256,
    }


def _seal_hypothesis(row):
    row = deepcopy(row)
    for field in ("research_claim_ids", "replacement_comparator_ids"):
        row[field] = sorted(row[field])
    row.pop("semantic_hash", None)
    row.pop("record_hash", None)
    semantic = deepcopy(row)
    semantic.pop("recorded_at")
    row["semantic_hash"] = canonical_hash(semantic)
    record = deepcopy(row)
    row["record_hash"] = canonical_hash(record)
    return row


def _hypothesis(*, claims=None, **overrides):
    claims = [_claim()] if claims is None else list(claims)
    row = {
        "schema_version": 1,
        "record_type": "v2_hypothesis_candidate",
        "candidate_id": "hypothesis-official-event-entry-v1",
        "hypothesis": "Confirmed official events change the next eligible decision surface.",
        "mechanism": {
            "economic_mechanism": "Slow incorporation of a timestamped official state change.",
            "causal_chain": [
                "official state becomes known",
                "eligible universe state changes",
                "next-session candidate set changes",
            ],
            "decision_surface": "candidate_pool",
            "why_not_arbitraged": "Point-in-time revisions and mapping costs limit simple reuse.",
        },
        "research_claim_ids": [item["claim_id"] for item in claims],
        "claim_snapshot_sha256": research_claim_snapshot_hash(claims),
        "novelty_axis": "independent_source",
        "novelty_basis": "Uses an official clocked source absent from the baseline.",
        "prior_fingerprint_snapshot_sha256": "2" * 64,
        "baseline_policy": _policy("v1-frozen-baseline", "3" * 64),
        "treatment_policy": _policy("v2-event-treatment", "4" * 64),
        "expected_horizon": "next eligible XNYS session",
        "replacement_comparator_ids": ["cash", "SPY", "QQQ", "V1"],
        "success_criteria": ["Coverage remains complete under replay."],
        "failure_conditions": ["The PIT clock cannot be reconstructed."],
        "falsifier": "The frozen treatment never changes an eligible candidate decision.",
        "kill_switches": ["Any future information enters a decision snapshot."],
        "promotion_conditions": ["Observed-only evidence survives the predeclared audit."],
        "execution_constraints": {
            "liquidity_rule": "Use the locked minimum-liquidity rule.",
            "capacity_rule": "Do not exceed the locked capacity ceiling.",
            "timing_rule": "Act no earlier than the next eligible session.",
            "overlap_rule": "Apply the frozen overlap rule.",
            "concentration_rule": "Apply the frozen concentration cap.",
        },
        "pit_tier": "research_pit",
        "result_ceiling": "observed_only",
        "known_future_leakage": False,
        "data_cutoff": "2026-08-20T14:05:00Z",
        "created_at": "2026-08-20T14:06:00Z",
        "frozen_at": "2026-08-20T14:07:00Z",
        "recorded_at": "2026-08-20T14:08:00Z",
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    row.update(overrides)
    return _seal_hypothesis(row)


def _event_for(*, evidence, mapping, **overrides):
    rule_sha256 = overrides.get("rule_sha256", "d" * 64)
    row = _event(evidence=evidence, security_mapping=mapping, **overrides)
    row["input_snapshot_sha256"] = universe_input_snapshot_hash(
        [evidence],
        rule_sha256=rule_sha256,
        security_mapping_sha256=mapping["mapping_sha256"],
        session_clock_id=row["session_clock_id"],
        session_clock_hash=row["session_clock_hash"],
        session_clock_record_hash=row["session_clock_record_hash"],
        effective_session_clock_id=row["effective_session_clock_id"],
        effective_session_clock_hash=row["effective_session_clock_hash"],
        effective_session_clock_record_hash=row[
            "effective_session_clock_record_hash"
        ],
    )
    return _seal_event(row)


def _transition(previous, *, evidence, to_state, suffix, minute):
    return _event_for(
        evidence=evidence,
        mapping=previous["security_mapping"],
        event_id=f"{previous['security_mapping']['security_id']}-{suffix}",
        event_type="state_transition",
        from_state=previous["to_state"],
        to_state=to_state,
        previous_event_id=previous["event_id"],
        previous_event_hash=previous["event_hash"],
        reason_code=f"transition_{to_state}",
        reason=f"Frozen rule changed the state to {to_state}.",
        pit_tier=previous["pit_tier"],
        known_future_leakage=previous["known_future_leakage"],
        decided_at=f"2026-08-20T14:{minute:02d}:00Z",
        recorded_at=f"2026-08-20T14:{minute + 1:02d}:00Z",
        effective_at=f"2026-08-20T14:{minute + 2:02d}:00Z",
    )


def _universe_chain(evidence, *, security_suffix="aaa"):
    mapping = evidence["security_mapping"]
    discovery = _event_for(
        evidence=evidence,
        mapping=mapping,
        event_id=f"sec-{security_suffix}-discovered",
        pit_tier=evidence["pit_tier"],
        known_future_leakage=evidence["known_future_leakage"],
    )
    research = _transition(
        discovery,
        evidence=evidence,
        to_state="research_eligible",
        suffix="research-eligible",
        minute=7,
    )
    eligible = _transition(
        research,
        evidence=evidence,
        to_state="candidate_eligible",
        suffix="candidate-eligible",
        minute=10,
    )
    return [discovery, research, eligible]


def _comparators():
    identities = {"cash": "cash", "spy": "SPY", "qqq": "QQQ", "v1": "V1"}
    return [
        {
            "role": role,
            "reference_id": identities[role],
            "reference_snapshot_sha256": f"{index:x}" * 64,
            "availability_status": "available",
            "reason_code": "required_replacement_panel",
            "reason": "Frozen replacement comparator for this decision.",
            "comparison_only": True,
        }
        for index, role in enumerate(("cash", "spy", "qqq", "v1"), start=5)
    ]


def _entry(*, hypothesis, event, evidence, entry_id=None):
    generator_rule_sha256 = "9" * 64
    return {
        "candidate_entry_id": entry_id or f"entry-{event['security_mapping']['security_id']}",
        "security_id": event["security_mapping"]["security_id"],
        "listing_id": event["security_mapping"]["listing_id"],
        "universe_event_id": event["event_id"],
        "security_mapping_sha256": event["security_mapping"]["mapping_sha256"],
        "evidence_record_ids": [evidence["evidence_id"]],
        "decision_input_sha256": candidate_entry_input_snapshot_hash(
            hypothesis_candidate=hypothesis,
            universe_event=event,
            evidence_records=[evidence],
            generator_rule_sha256=generator_rule_sha256,
        ),
        "admission_status": "admitted",
        "reason_code": "frozen_rule_pass",
        "reason": "Candidate passed the outcome-blind frozen generator rule.",
    }


def _seal_pool(row):
    row = deepcopy(row)
    for field in ("universe_event_ids", "evidence_record_ids"):
        row[field] = sorted(row[field])
    for entry in row["entries"]:
        entry["evidence_record_ids"] = sorted(entry["evidence_record_ids"])
    row["entries"] = sorted(row["entries"], key=lambda item: item["candidate_entry_id"])
    row["comparators"] = sorted(row["comparators"], key=lambda item: item["role"])
    row.pop("semantic_hash", None)
    row.pop("record_hash", None)
    semantic = deepcopy(row)
    semantic.pop("recorded_at")
    row["semantic_hash"] = canonical_hash(semantic)
    record = deepcopy(row)
    row["record_hash"] = canonical_hash(record)
    return row


def _pool(*, hypothesis, evidence_records, events, entries=None, **overrides):
    evidence_records = list(evidence_records)
    events = list(events)
    if entries is None:
        evidence_by_security = {
            item["security_mapping"]["security_id"]: item for item in evidence_records
        }
        entries = [
            _entry(
                hypothesis=hypothesis,
                event=event,
                evidence=evidence_by_security[event["security_mapping"]["security_id"]],
            )
            for event in events
            if event["to_state"] == "candidate_eligible"
        ]
    entries = list(entries)
    comparators = _comparators()
    generator_rule_sha256 = "9" * 64
    ranking_rule_sha256 = "a" * 64
    data_cutoff = overrides.get("data_cutoff", "2026-08-20T14:12:00Z")
    row = {
        "schema_version": 2,
        "record_type": "v2_candidate_pool",
        "candidate_pool_id": "candidate-pool-20260820-v1",
        "hypothesis_candidate_id": hypothesis["candidate_id"],
        "hypothesis_candidate_hash": hypothesis["semantic_hash"],
        "universe_id": "v2-research-universe",
        "universe_event_ids": [item["event_id"] for item in events],
        "universe_event_snapshot_sha256": universe_event_snapshot_hash(events),
        "evidence_record_ids": [item["evidence_id"] for item in evidence_records],
        "evidence_snapshot_sha256": research_evidence_snapshot_hash(evidence_records),
        "entries": entries,
        "comparators": comparators,
        "generator_rule_id": "candidate-generator",
        "generator_rule_version": "1",
        "generator_rule_sha256": generator_rule_sha256,
        "ranking_rule_id": "candidate-ranking-inputs",
        "ranking_rule_version": "1",
        "ranking_rule_sha256": ranking_rule_sha256,
        "run_id": "candidate-pool-run-20260820-v1",
        "session_clock_id": "clock-v2-run-20260820",
        "session_clock_hash": "f" * 64,
        "session_clock_record_hash": "e" * 64,
        "run_date": "2026-08-20",
        "calendar_session_id": "XNYS-2026-08-20",
        "data_cutoff": data_cutoff,
        "frozen_at": "2026-08-20T14:13:00Z",
        "recorded_at": "2026-08-20T14:14:00Z",
        "expected_candidate_count": len(entries),
        "candidate_pool_complete": True,
        "universe_snapshot_complete": True,
        "input_snapshot_sha256": candidate_pool_input_snapshot_hash(
            hypothesis_candidate=hypothesis,
            evidence_records=evidence_records,
            universe_events=events,
            entries=entries,
            comparators=comparators,
            generator_rule_sha256=generator_rule_sha256,
            ranking_rule_sha256=ranking_rule_sha256,
            universe_id="v2-research-universe",
            session_clock_id="clock-v2-run-20260820",
            session_clock_hash="f" * 64,
            session_clock_record_hash="e" * 64,
            run_date="2026-08-20",
            calendar_session_id="XNYS-2026-08-20",
            data_cutoff=data_cutoff,
        ),
        "pit_tier": hypothesis["pit_tier"],
        "result_ceiling": hypothesis["result_ceiling"],
        "known_future_leakage": hypothesis["known_future_leakage"],
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    row.update(overrides)
    return _seal_pool(row)


def _graph(*, pit_tier="research_pit", leakage=False, two_candidates=False):
    source = _source()
    evidence_a = _evidence(
        source=source,
        pit_tier=pit_tier,
        known_future_leakage=leakage,
    )
    evidence = [evidence_a]
    events = _universe_chain(evidence_a)
    if two_candidates:
        mapping_b = _mapping(
            mapping_id="map-sec-bbb-xnys-v1",
            security_id="sec-bbb",
            listing_id="listing-bbb-xnys",
            symbol="BBB",
            mic="XNYS",
        )
        evidence_b = _evidence(
            source=source,
            evidence_id="evidence-official-event-2-r1",
            raw_identity={"event_id": "event-2", "revision_id": "r1"},
            raw_artifact_locator="raw/official/event-2-r1.json",
            security_mapping=mapping_b,
            pit_tier=pit_tier,
            known_future_leakage=leakage,
        )
        evidence.append(evidence_b)
        chain_b = _universe_chain(evidence_b, security_suffix="bbb")
        events.extend(chain_b)
    claim = _claim(
        evidence_records=evidence,
        affected_object_ids=[item["security_mapping"]["security_id"] for item in evidence],
        pit_tier=pit_tier,
        known_future_leakage=leakage,
    )
    ceiling = {
        "not_pit": "invalid",
        "research_pit": "observed_only",
        "canonical_pit": "gate_eligible",
    }[pit_tier]
    hypothesis = _hypothesis(
        claims=[claim],
        pit_tier=pit_tier,
        result_ceiling=ceiling,
        known_future_leakage=leakage,
    )
    pool = _pool(
        hypothesis=hypothesis,
        evidence_records=evidence,
        events=events,
    )
    return {
        "source": source,
        "evidence": evidence,
        "claim": claim,
        "hypothesis": hypothesis,
        "events": events,
        "pool": pool,
    }


def _validate_graph(graph):
    return validate_candidate_pool_against_inputs(
        graph["pool"],
        graph["hypothesis"],
        [graph["claim"]],
        graph["evidence"],
        [graph["source"]],
        graph["events"],
    )


def test_research_claim_round_trip_hash_and_input_are_stable():
    graph = _graph()
    row = graph["claim"]
    original = deepcopy(row)

    claim = validate_research_claim_against_evidence(
        row, graph["evidence"], [graph["source"]]
    )

    assert isinstance(claim, ResearchClaim)
    assert row == original
    assert normalize_research_claim(claim) == normalize_research_claim(row)
    assert claim.canonical_hash == canonical_hash(claim.to_dict())


def test_hypothesis_round_trip_hash_and_input_are_stable():
    graph = _graph()
    row = graph["hypothesis"]
    original = deepcopy(row)

    candidate = validate_hypothesis_candidate_against_claims(
        row, [graph["claim"]], graph["evidence"], [graph["source"]]
    )

    assert isinstance(candidate, HypothesisCandidate)
    assert row == original
    assert normalize_hypothesis_candidate(candidate) == normalize_hypothesis_candidate(row)
    assert candidate.canonical_hash == canonical_hash(candidate.to_dict())


def test_candidate_pool_round_trip_hash_and_full_input_chain_are_stable():
    graph = _graph()
    row = graph["pool"]
    originals = deepcopy(graph)

    pool = _validate_graph(graph)

    assert isinstance(pool, CandidatePool)
    assert graph == originals
    assert normalize_candidate_pool(pool) == normalize_candidate_pool(row)
    assert pool.canonical_hash == canonical_hash(pool.to_dict())
    assert pool.trade_enabled is False


def test_dataclass_instances_are_revalidated_instead_of_trusted():
    graph = _graph()
    claim = validate_research_claim(graph["claim"])
    hypothesis = validate_hypothesis_candidate(graph["hypothesis"])
    pool = validate_candidate_pool(graph["pool"])

    _assert_code(
        "research_authority_required",
        lambda: validate_research_claim(replace(claim, authority="trading")),
    )
    _assert_code(
        "results_accessed_forbidden",
        lambda: validate_hypothesis_candidate(replace(hypothesis, results_accessed=True)),
    )
    _assert_code(
        "candidate_pool_incomplete",
        lambda: validate_candidate_pool(replace(pool, candidate_pool_complete=False)),
    )
    _assert_code(
        "trade_enabled_forbidden",
        lambda: validate_candidate_pool(replace(pool, trade_enabled=True)),
    )


@pytest.mark.parametrize(
    ("builder", "mutator", "code"),
    [
        (_claim, lambda row: row.pop("falsifier"), "missing_field"),
        (_claim, lambda row: row.update(realized_return_bps=120), "unknown_field"),
        (
            _hypothesis,
            lambda row: row.pop("failure_conditions"),
            "missing_field",
        ),
        (
            _hypothesis,
            lambda row: row["mechanism"].update(realized_pnl=1.0),
            "unknown_field",
        ),
        (
            _hypothesis,
            lambda row: row["baseline_policy"].update(selected_rank=1),
            "unknown_field",
        ),
    ],
)
def test_claim_and_hypothesis_reject_missing_unknown_outcome_and_rank_fields(
    builder, mutator, code
):
    row = builder()
    mutator(row)
    validator = (
        validate_research_claim if builder is _claim else validate_hypothesis_candidate
    )
    _assert_code(code, lambda: validator(row))


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (lambda row: row.pop("entries"), "missing_field"),
        (
            lambda row: row["entries"][0].update(forward_return=0.2),
            "unknown_field",
        ),
        (
            lambda row: row["comparators"][0].update(selected_rank=1),
            "unknown_field",
        ),
        (lambda row: row.update(realized_sharpe=3.0), "unknown_field"),
    ],
)
def test_candidate_pool_rejects_missing_nested_or_root_outcome_and_rank_fields(
    mutator, code
):
    row = _graph()["pool"]
    mutator(row)
    _assert_code(code, lambda: validate_candidate_pool(row))


@pytest.mark.parametrize(
    ("kind", "field", "value", "code"),
    [
        ("claim", "outcome_blind", False, "outcome_blind_required"),
        ("claim", "authority", "trade", "research_authority_required"),
        ("claim", "trade_enabled", True, "trade_enabled_forbidden"),
        ("hypothesis", "results_accessed", True, "results_accessed_forbidden"),
        ("hypothesis", "trade_enabled", True, "trade_enabled_forbidden"),
        ("pool", "outcome_blind", False, "outcome_blind_required"),
        ("pool", "results_accessed", True, "results_accessed_forbidden"),
        ("pool", "authority", "allocator", "research_authority_required"),
        ("pool", "trade_enabled", True, "trade_enabled_forbidden"),
    ],
)
def test_research_records_are_outcome_blind_research_only_and_default_off(
    kind, field, value, code
):
    graph = _graph()
    row = graph[kind]
    row[field] = value
    validator = {
        "claim": validate_research_claim,
        "hypothesis": validate_hypothesis_candidate,
        "pool": validate_candidate_pool,
    }[kind]
    _assert_code(code, lambda: validator(row))


@pytest.mark.parametrize(
    ("kind", "field", "value", "code"),
    [
        ("claim", "as_of", "2026-08-20", "instant_required"),
        ("claim", "known_at", "2026-08-20T14:03:00Z", "invalid_claim_chronology"),
        ("hypothesis", "data_cutoff", "2026-08-20T14:07:00Z", "invalid_hypothesis_chronology"),
        ("pool", "data_cutoff", "2026-08-20T14:14:00Z", "invalid_candidate_pool_chronology"),
    ],
)
def test_research_record_clocks_fail_closed(kind, field, value, code):
    row = _graph()[kind]
    row[field] = value
    validator = {
        "claim": validate_research_claim,
        "hypothesis": validate_hypothesis_candidate,
        "pool": validate_candidate_pool,
    }[kind]
    _assert_code(code, lambda: validator(row))


@pytest.mark.parametrize("kind", ["claim", "hypothesis", "pool"])
def test_pit_tier_cannot_be_escalated_above_weakest_cross_chain_input(kind):
    graph = _graph(pit_tier="not_pit", leakage=True)
    row = graph[kind]
    row["pit_tier"] = "research_pit"
    if kind != "claim":
        row["result_ceiling"] = "observed_only"
    row["known_future_leakage"] = False
    row = {
        "claim": _seal_claim,
        "hypothesis": _seal_hypothesis,
        "pool": _seal_pool,
    }[kind](row)
    if kind == "claim":
        call = lambda: validate_research_claim_against_evidence(
            row, graph["evidence"], [graph["source"]]
        )
        code = "pit_tier_exceeds_evidence"
    elif kind == "hypothesis":
        call = lambda: validate_hypothesis_candidate_against_claims(
            row, [graph["claim"]], graph["evidence"], [graph["source"]]
        )
        code = "pit_tier_exceeds_claim"
    else:
        graph["pool"] = row
        call = lambda: _validate_graph(graph)
        code = "pit_tier_exceeds_pool_inputs"
    _assert_code(code, call)


@pytest.mark.parametrize("kind", ["claim", "hypothesis", "pool"])
def test_future_leakage_must_propagate_through_every_research_layer(kind):
    graph = _graph(pit_tier="not_pit", leakage=True)
    row = graph[kind]
    row["known_future_leakage"] = False
    row = {
        "claim": _seal_claim,
        "hypothesis": _seal_hypothesis,
        "pool": _seal_pool,
    }[kind](row)
    if kind == "claim":
        call = lambda: validate_research_claim_against_evidence(
            row, graph["evidence"], [graph["source"]]
        )
    elif kind == "hypothesis":
        call = lambda: validate_hypothesis_candidate_against_claims(
            row, [graph["claim"]], graph["evidence"], [graph["source"]]
        )
    else:
        graph["pool"] = row
        call = lambda: _validate_graph(graph)
    _assert_code("future_leakage_not_propagated", call)


def test_claim_requires_resolved_source_evidence_and_exact_snapshot():
    graph = _graph()
    validate_research_claim_against_evidence(
        graph["claim"], graph["evidence"], [graph["source"]]
    )
    _assert_code(
        "unresolved_evidence_id",
        lambda: validate_research_claim_against_evidence(
            graph["claim"], [], [graph["source"]]
        ),
    )
    _assert_code(
        "unresolved_source_contract_id",
        lambda: validate_research_claim_against_evidence(
            graph["claim"], graph["evidence"], []
        ),
    )
    tampered = _seal_claim(
        {**graph["claim"], "evidence_snapshot_sha256": "b" * 64}
    )
    _assert_code(
        "evidence_snapshot_hash_mismatch",
        lambda: validate_research_claim_against_evidence(
            tampered, graph["evidence"], [graph["source"]]
        ),
    )


def test_hypothesis_requires_resolved_claims_and_exact_snapshot():
    graph = _graph()
    validate_hypothesis_candidate_against_claims(
        graph["hypothesis"],
        [graph["claim"]],
        graph["evidence"],
        [graph["source"]],
    )
    _assert_code(
        "unresolved_claim_id",
        lambda: validate_hypothesis_candidate_against_claims(
            graph["hypothesis"], [], graph["evidence"], [graph["source"]]
        ),
    )
    tampered = _seal_hypothesis(
        {**graph["hypothesis"], "claim_snapshot_sha256": "b" * 64}
    )
    _assert_code(
        "claim_snapshot_hash_mismatch",
        lambda: validate_hypothesis_candidate_against_claims(
            tampered,
            [graph["claim"]],
            graph["evidence"],
            [graph["source"]],
        ),
    )


def test_pool_requires_exact_hypothesis_evidence_and_universe_membership():
    graph = _graph()
    _validate_graph(graph)

    wrong_hypothesis = _seal_pool(
        {**graph["pool"], "hypothesis_candidate_id": "different-hypothesis"}
    )
    graph["pool"] = wrong_hypothesis
    _assert_code("hypothesis_candidate_id_mismatch", lambda: _validate_graph(graph))

    graph = _graph()
    extra = _evidence(
        source=graph["source"],
        evidence_id="evidence-extra-r1",
        raw_identity={"event_id": "event-extra", "revision_id": "r1"},
        raw_artifact_locator="raw/official/event-extra-r1.json",
    )
    _assert_code(
        "evidence_snapshot_membership_mismatch",
        lambda: validate_candidate_pool_against_inputs(
            graph["pool"],
            graph["hypothesis"],
            [graph["claim"]],
            [*graph["evidence"], extra],
            [graph["source"]],
            graph["events"],
        ),
    )
    _assert_code(
        "universe_snapshot_membership_mismatch",
        lambda: validate_candidate_pool_against_inputs(
            graph["pool"],
            graph["hypothesis"],
            [graph["claim"]],
            graph["evidence"],
            [graph["source"]],
            graph["events"][:-1],
        ),
    )


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (lambda row: row["comparators"].pop(), "comparator_panel_incomplete"),
        (
            lambda row: row["comparators"].__setitem__(
                1, deepcopy(row["comparators"][0])
            ),
            "comparator_panel_incomplete",
        ),
        (
            lambda row: row.update(expected_candidate_count=2),
            "candidate_count_mismatch",
        ),
        (
            lambda row: row.update(candidate_pool_complete=False),
            "candidate_pool_incomplete",
        ),
        (
            lambda row: row.update(universe_snapshot_complete=False),
            "universe_snapshot_incomplete",
        ),
        (
            lambda row: row["entries"].append(deepcopy(row["entries"][0])),
            "duplicate_candidate_entry_id",
        ),
        (
            lambda row: row["entries"].append(
                {
                    **deepcopy(row["entries"][0]),
                    "candidate_entry_id": "entry-duplicate-security",
                }
            ),
            "duplicate_candidate_security",
        ),
    ],
)
def test_pool_requires_exact_comparator_panel_counts_completeness_and_unique_entries(
    mutator, code
):
    row = _graph()["pool"]
    mutator(row)
    _assert_code(code, lambda: validate_candidate_pool(row))


def test_complete_zero_candidate_pool_is_valid_and_keeps_all_four_comparators():
    graph = _graph()
    graph["events"] = graph["events"][:2]
    graph["pool"] = _pool(
        hypothesis=graph["hypothesis"],
        evidence_records=graph["evidence"],
        events=graph["events"],
    )

    pool = _validate_graph(graph)

    assert pool.entries == ()
    assert pool.expected_candidate_count == 0
    assert pool.candidate_pool_complete is True
    assert {item.reference_id for item in pool.comparators} == {
        "cash",
        "SPY",
        "QQQ",
        "V1",
    }


def test_comparator_roles_must_bind_exact_cash_spy_qqq_and_v1_identities():
    graph = _graph()
    row = deepcopy(graph["pool"])
    spy = next(item for item in row["comparators"] if item["role"] == "spy")
    spy["reference_id"] = "SPY-adjusted"
    graph["pool"] = _seal_pool(row)

    _assert_code("comparator_identity_mismatch", lambda: _validate_graph(graph))


def test_pool_uses_latest_candidate_eligible_state_only():
    graph = _graph()
    discovery, research, eligible = graph["events"]
    stale_entry = _entry(
        hypothesis=graph["hypothesis"],
        event=eligible,
        evidence=graph["evidence"][0],
    )
    downgraded = _transition(
        eligible,
        evidence=graph["evidence"][0],
        to_state="research_eligible",
        suffix="downgraded",
        minute=13,
    )
    restored = _transition(
        downgraded,
        evidence=graph["evidence"][0],
        to_state="candidate_eligible",
        suffix="restored",
        minute=16,
    )
    events = [discovery, research, eligible, downgraded, restored]
    pool = _pool(
        hypothesis=graph["hypothesis"],
        evidence_records=graph["evidence"],
        events=events,
        entries=[stale_entry],
        data_cutoff="2026-08-20T14:18:00Z",
        frozen_at="2026-08-20T14:19:00Z",
        recorded_at="2026-08-20T14:20:00Z",
    )
    graph.update(pool=pool, events=events)

    _assert_code(
        "candidate_not_bound_to_latest_universe_event", lambda: _validate_graph(graph)
    )

    no_eligible_events = [discovery, research]
    pool = _pool(
        hypothesis=graph["hypothesis"],
        evidence_records=graph["evidence"],
        events=no_eligible_events,
        entries=[
            _entry(
                hypothesis=graph["hypothesis"],
                event=research,
                evidence=graph["evidence"][0],
            )
        ],
    )
    graph.update(pool=pool, events=no_eligible_events)
    _assert_code("candidate_surface_incomplete", lambda: _validate_graph(graph))


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("evidence_snapshot_sha256", "evidence_snapshot_hash_mismatch"),
        ("universe_event_snapshot_sha256", "universe_event_snapshot_hash_mismatch"),
        ("input_snapshot_sha256", "input_snapshot_hash_mismatch"),
    ],
)
def test_pool_snapshot_tampering_is_rejected(field, code):
    graph = _graph()
    graph["pool"] = _seal_pool({**graph["pool"], field: "b" * 64})
    _assert_code(code, lambda: _validate_graph(graph))


def test_candidate_entry_input_snapshot_tampering_is_rejected():
    graph = _graph()
    row = deepcopy(graph["pool"])
    row["entries"][0]["decision_input_sha256"] = "b" * 64
    graph["pool"] = _seal_pool(row)
    _assert_code("candidate_entry_input_hash_mismatch", lambda: _validate_graph(graph))


def test_transition_decision_cannot_predate_prior_recorded_and_effective_state():
    graph = _graph()
    discovery = graph["events"][0]
    early_transition = _event_for(
        evidence=graph["evidence"][0],
        mapping=discovery["security_mapping"],
        event_id="sec-aaa-early-transition",
        event_type="state_transition",
        from_state="discovered",
        to_state="research_eligible",
        previous_event_id=discovery["event_id"],
        previous_event_hash=discovery["event_hash"],
        reason_code="early_transition",
        reason="A transition decided before the prior state became effective.",
        decided_at="2026-08-20T14:04:30Z",
        recorded_at="2026-08-20T14:05:30Z",
        effective_at="2026-08-20T14:06:30Z",
    )
    graph["events"] = [discovery, early_transition]
    graph["pool"] = _pool(
        hypothesis=graph["hypothesis"],
        evidence_records=graph["evidence"],
        events=graph["events"],
    )

    _assert_code(
        "universe_transition_before_prior_effective", lambda: _validate_graph(graph)
    )


def test_fractional_second_transition_chain_is_sorted_by_parsed_instant():
    graph = _graph()
    discovery = graph["events"][0]
    fractional_transition = _event_for(
        evidence=graph["evidence"][0],
        mapping=discovery["security_mapping"],
        event_id="sec-aaa-fractional-transition",
        event_type="state_transition",
        from_state="discovered",
        to_state="research_eligible",
        previous_event_id=discovery["event_id"],
        previous_event_hash=discovery["event_hash"],
        reason_code="fractional_transition",
        reason="A valid transition half a second after discovery became effective.",
        decided_at="2026-08-20T14:06:00Z",
        recorded_at="2026-08-20T14:06:00.250000Z",
        effective_at="2026-08-20T14:06:00.500000Z",
    )
    graph["events"] = [fractional_transition, discovery]
    graph["pool"] = _pool(
        hypothesis=graph["hypothesis"],
        evidence_records=graph["evidence"],
        events=graph["events"],
    )

    pool = _validate_graph(graph)

    assert pool.expected_candidate_count == 0
    assert pool.universe_snapshot_complete is True


def test_source_and_evidence_leakage_cannot_be_dropped_and_propagates_end_to_end():
    source = _source(maximum_pit_tier="not_pit", known_future_leakage=True)
    dropped_evidence = _evidence(
        source=source,
        pit_tier="not_pit",
        known_future_leakage=False,
    )
    _assert_code(
        "future_leakage_not_propagated",
        lambda: validate_evidence_against_source(dropped_evidence, source),
    )

    evidence = _evidence(
        source=source,
        pit_tier="not_pit",
        known_future_leakage=True,
    )
    dropped_event = _event_for(
        evidence=evidence,
        mapping=evidence["security_mapping"],
        pit_tier="not_pit",
        known_future_leakage=False,
    )
    _assert_code(
        "future_leakage_not_propagated",
        lambda: validate_universe_event_against_evidence(
            dropped_event, [evidence], [source]
        ),
    )

    events = _universe_chain(evidence)
    claim = _claim(
        evidence_records=[evidence],
        pit_tier="not_pit",
        known_future_leakage=True,
    )
    hypothesis = _hypothesis(
        claims=[claim],
        pit_tier="not_pit",
        result_ceiling="invalid",
        known_future_leakage=True,
    )
    pool = _pool(
        hypothesis=hypothesis,
        evidence_records=[evidence],
        events=events,
    )
    graph = {
        "source": source,
        "evidence": [evidence],
        "claim": claim,
        "hypothesis": hypothesis,
        "events": events,
        "pool": pool,
    }

    validated = _validate_graph(graph)

    assert evidence["known_future_leakage"] is True
    assert all(event["known_future_leakage"] for event in events)
    assert claim["known_future_leakage"] is True
    assert hypothesis["known_future_leakage"] is True
    assert validated.known_future_leakage is True


def test_candidate_entries_cannot_swap_instrument_evidence_after_full_reseal():
    graph = _graph(two_candidates=True)
    evidence_by_security = {
        item["security_mapping"]["security_id"]: item for item in graph["evidence"]
    }
    event_by_id = {item["event_id"]: item for item in graph["events"]}
    swapped_entries = []
    for entry in graph["pool"]["entries"]:
        other_security = "sec-bbb" if entry["security_id"] == "sec-aaa" else "sec-aaa"
        other_evidence = evidence_by_security[other_security]
        swapped = deepcopy(entry)
        swapped["evidence_record_ids"] = [other_evidence["evidence_id"]]
        swapped["decision_input_sha256"] = candidate_entry_input_snapshot_hash(
            hypothesis_candidate=graph["hypothesis"],
            universe_event=event_by_id[entry["universe_event_id"]],
            evidence_records=[other_evidence],
            generator_rule_sha256=graph["pool"]["generator_rule_sha256"],
        )
        swapped_entries.append(swapped)
    graph["pool"] = _pool(
        hypothesis=graph["hypothesis"],
        evidence_records=graph["evidence"],
        events=graph["events"],
        entries=swapped_entries,
    )

    validate_candidate_pool(graph["pool"])
    _assert_code("candidate_evidence_security_mismatch", lambda: _validate_graph(graph))


def test_set_like_inputs_and_pool_surfaces_normalize_order_without_changing_hashes():
    graph = _graph(two_candidates=True)
    expected = _validate_graph(graph)
    reordered = deepcopy(graph)
    reordered["claim"]["evidence_record_ids"].reverse()
    reordered["claim"]["affected_object_ids"].reverse()
    reordered["hypothesis"]["replacement_comparator_ids"].reverse()
    reordered["pool"]["evidence_record_ids"].reverse()
    reordered["pool"]["universe_event_ids"].reverse()
    reordered["pool"]["entries"].reverse()
    reordered["pool"]["comparators"].reverse()
    reordered["evidence"].reverse()
    reordered["events"].reverse()

    actual = _validate_graph(reordered)

    assert actual.to_dict() == expected.to_dict()
    assert actual.record_hash == expected.record_hash
    assert research_evidence_snapshot_hash(
        reordered["evidence"]
    ) == research_evidence_snapshot_hash(graph["evidence"])
    assert universe_event_snapshot_hash(
        reordered["events"]
    ) == universe_event_snapshot_hash(graph["events"])
