from copy import deepcopy
from collections.abc import Mapping, Sequence

import pytest

from quant.test_v2_contracts import _seal_event
from quant.test_v2_engine0_baseline import (
    _inputs,
    _inputs_with_quarantine_membership,
    _refresh_pool_graph,
    _reseal_market_clock_memberships,
)
from quant.v2_contracts import canonical_hash
from quant.v2_dynamic_market_universe import (
    V2DynamicMarketUniverseError,
    build_daily_research_only_dynamic_market_universe_snapshot,
    build_replay_research_only_dynamic_market_universe_snapshot,
    build_research_only_dynamic_market_universe_snapshot,
    validate_dynamic_market_universe_snapshot,
)
from quant.v2_universe_ledger import validate_universe_event_population


def _build(inputs):
    return build_research_only_dynamic_market_universe_snapshot(
        inputs["market_clock_snapshot"],
        inputs["candidate_pool"],
        inputs["hypothesis_candidate"],
        inputs["research_claims"],
        inputs["decision_evidence_records"],
        inputs["decision_source_contracts"],
        inputs["universe_events"],
        inputs["session_clock"],
        inputs["calendar_sessions"],
        inputs["calendar_evidence"],
        inputs["calendar_source_contract"],
        expected_market_clock_snapshot_hash=inputs[
            "expected_market_clock_snapshot_hash"
        ],
        expected_research_input_identity=inputs[
            "expected_research_input_identity"
        ],
    )


def _validate(inputs):
    return validate_dynamic_market_universe_snapshot(
        inputs["dynamic_market_universe_snapshot"],
        inputs["market_clock_snapshot"],
        inputs["candidate_pool"],
        inputs["hypothesis_candidate"],
        inputs["research_claims"],
        inputs["decision_evidence_records"],
        inputs["decision_source_contracts"],
        inputs["universe_events"],
        inputs["session_clock"],
        inputs["calendar_sessions"],
        inputs["calendar_evidence"],
        inputs["calendar_source_contract"],
        expected_snapshot_hash=inputs[
            "expected_dynamic_market_universe_snapshot_hash"
        ],
        expected_market_clock_snapshot_hash=inputs[
            "expected_market_clock_snapshot_hash"
        ],
        expected_research_input_identity=inputs[
            "expected_research_input_identity"
        ],
    )


def _assert_code(code, func):
    with pytest.raises(V2DynamicMarketUniverseError) as caught:
        func()
    assert caught.value.code == code
    return caught.value


def _reseal_snapshot(snapshot):
    snapshot = deepcopy(snapshot)
    snapshot.pop("dynamic_market_universe_snapshot_hash", None)
    snapshot["dynamic_market_universe_snapshot_hash"] = canonical_hash(snapshot)
    return snapshot


def _reseal_lineage(snapshot):
    snapshot = deepcopy(snapshot)
    lineage = snapshot["membership_lineage"]
    for row in lineage["rows"]:
        row.pop("lineage_row_sha256", None)
        row["lineage_row_sha256"] = canonical_hash(row)
    lineage["membership_count"] = len(lineage["rows"])
    lineage["row_snapshot_sha256"] = canonical_hash(lineage["rows"])
    lineage.pop("membership_lineage_sha256", None)
    lineage["membership_lineage_sha256"] = canonical_hash(lineage)
    snapshot["membership_lineage_sha256"] = lineage[
        "membership_lineage_sha256"
    ]
    return _reseal_snapshot(snapshot)


def test_golden_snapshot_is_exact_source_bound_dynamic_pit_universe():
    inputs = _inputs()
    snapshot = _validate(inputs)
    lineage = snapshot["membership_lineage"]

    assert _build(deepcopy(inputs)) == snapshot
    assert snapshot["dynamic_market_universe_contract"] == (
        "v2_research_only_dynamic_pit_market_universe_v1"
    )
    assert snapshot["dynamic_market_universe_status"] == (
        "verified_exact_rows_research_only"
    )
    assert snapshot["market_universe_scope"] == (
        "source_bound_post_candidate_pool_reconciliation"
    )
    assert snapshot["state_counts"] == {
        "discovered": 0,
        "research_eligible": 0,
        "candidate_eligible": 2,
        "quarantine": 0,
        "retired": 0,
    }
    assert lineage["membership_count"] == len(
        inputs["market_clock_snapshot"]["memberships"]
    )
    assert lineage["row_snapshot_sha256"] == canonical_hash(lineage["rows"])
    assert snapshot["membership_lineage_sha256"] == lineage[
        "membership_lineage_sha256"
    ]
    assert snapshot["external_universe_coverage_status"] == "unverified"
    assert snapshot["pit_tier"] == "research_pit"
    assert snapshot["result_ceiling"] == "observed_only"
    assert snapshot["runtime_parity_status"] == "unwired"
    assert snapshot["production_parity_status"] == "unwired"
    assert snapshot["paper_live_eligible"] is False
    assert snapshot["promotion_eligible"] is False
    assert snapshot["trade_enabled"] is False
    assert not {
        "features",
        "scores",
        "ranks",
        "signals",
        "sizes",
        "outcomes",
        "orders",
    } & set(snapshot)


def test_daily_replay_are_true_aliases_and_snapshot_is_deterministic():
    assert build_daily_research_only_dynamic_market_universe_snapshot is (
        build_research_only_dynamic_market_universe_snapshot
    )
    assert build_replay_research_only_dynamic_market_universe_snapshot is (
        build_research_only_dynamic_market_universe_snapshot
    )
    inputs = _inputs()
    assert _build(inputs) == _build(deepcopy(inputs))


def test_separately_frozen_snapshot_hash_and_boundary_escalation_fail_closed():
    damaged = _inputs()
    damaged["dynamic_market_universe_snapshot"][
        "dynamic_market_universe_snapshot_hash"
    ] = "0" * 64
    _assert_code(
        "dynamic_market_universe_expected_hash_mismatch",
        lambda: _validate(damaged),
    )

    for field, value in (
        ("trade_enabled", True),
        ("trade_enabled", 0),
        ("external_universe_coverage_status", "verified"),
        ("pit_tier", "canonical_pit"),
        ("promotion_eligible", True),
    ):
        escalated = _inputs()
        snapshot = deepcopy(escalated["dynamic_market_universe_snapshot"])
        snapshot[field] = value
        snapshot = _reseal_snapshot(snapshot)
        escalated["dynamic_market_universe_snapshot"] = snapshot
        escalated["expected_dynamic_market_universe_snapshot_hash"] = snapshot[
            "dynamic_market_universe_snapshot_hash"
        ]
        _assert_code(
            "dynamic_market_universe_snapshot_dependency_mismatch",
            lambda escalated=escalated: _validate(escalated),
        )


def test_non_candidate_memberships_remain_in_the_complete_dynamic_surface():
    inputs = _inputs_with_quarantine_membership()
    snapshot = _validate(inputs)

    assert snapshot["input_identity"]["candidate_entry_count"] == 1
    assert snapshot["input_identity"]["membership_count"] == 2
    assert snapshot["state_counts"]["candidate_eligible"] == 1
    assert snapshot["state_counts"]["quarantine"] == 1
    assert [row["state"] for row in snapshot["membership_lineage"]["rows"]] == [
        "candidate_eligible",
        "quarantine",
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mapping_id", "map-resealed-crosswire"),
        ("state", "quarantine"),
        ("latest_event_id", "event-resealed-crosswire"),
        ("latest_event_semantic_hash", "e" * 64),
        ("latest_event_hash", "f" * 64),
        ("effective_at", "2026-08-20T14:11:59Z"),
    ],
)
def test_fully_resealed_membership_row_drift_fails_dependencies(field, value):
    inputs = _inputs()
    snapshot = deepcopy(inputs["dynamic_market_universe_snapshot"])
    snapshot["membership_lineage"]["rows"][0][field] = value
    snapshot = _reseal_lineage(snapshot)
    inputs["dynamic_market_universe_snapshot"] = snapshot
    inputs["expected_dynamic_market_universe_snapshot_hash"] = snapshot[
        "dynamic_market_universe_snapshot_hash"
    ]

    _assert_code(
        "dynamic_market_universe_snapshot_dependency_mismatch",
        lambda: _validate(inputs),
    )


def test_fully_resealed_lineage_truncation_fails_dependencies():
    inputs = _inputs_with_quarantine_membership()
    snapshot = deepcopy(inputs["dynamic_market_universe_snapshot"])
    snapshot["membership_lineage"]["rows"] = snapshot[
        "membership_lineage"
    ]["rows"][:1]
    snapshot = _reseal_lineage(snapshot)
    inputs["dynamic_market_universe_snapshot"] = snapshot
    inputs["expected_dynamic_market_universe_snapshot_hash"] = snapshot[
        "dynamic_market_universe_snapshot_hash"
    ]

    _assert_code(
        "dynamic_market_universe_snapshot_dependency_mismatch",
        lambda: _validate(inputs),
    )


def test_resealed_clock_truncation_still_fails_full_event_projection():
    inputs = _inputs_with_quarantine_membership()
    clock = deepcopy(inputs["market_clock_snapshot"])
    clock["memberships"] = clock["memberships"][:1]
    clock = _reseal_market_clock_memberships(clock)
    inputs["market_clock_snapshot"] = clock
    inputs["expected_market_clock_snapshot_hash"] = clock[
        "market_decision_clock_snapshot_hash"
    ]

    _assert_code(
        "dynamic_market_universe_membership_lineage_mismatch",
        lambda: _build(inputs),
    )


def test_exact_event_record_drift_fails_clock_lineage_even_when_semantics_match():
    inputs = _inputs()
    events = deepcopy(inputs["universe_events"])
    latest_index = next(
        index
        for index, event in enumerate(events)
        if event["event_id"] == "sec-aaa-candidate-eligible"
    )
    event = events[latest_index]
    event["recorded_at"] = "2026-08-20T14:11:30Z"
    events[latest_index] = _seal_event(event)
    inputs["universe_events"] = events

    _assert_code(
        "dynamic_market_universe_membership_lineage_mismatch",
        lambda: _build(inputs),
    )


def test_fully_resealed_event_population_truncation_cannot_hide_clock_row():
    inputs = _inputs_with_quarantine_membership()
    events = [
        event
        for event in deepcopy(inputs["universe_events"])
        if event["security_mapping"]["security_id"] != "sec-bbb"
    ]
    _refresh_pool_graph(inputs, events)

    _assert_code(
        "dynamic_market_universe_membership_lineage_mismatch",
        lambda: _build(inputs),
    )


def test_changing_event_sequence_is_materialized_once_before_validation():
    inputs = _inputs()
    first_events = deepcopy(inputs["universe_events"])
    second_events = deepcopy(first_events)
    latest_index = next(
        index
        for index, event in enumerate(second_events)
        if event["event_id"] == "sec-bbb-candidate-eligible"
    )
    alternate = second_events[latest_index]
    alternate["to_state"] = "quarantine"
    second_events[latest_index] = _seal_event(alternate)
    _, alternate_memberships = validate_universe_event_population(
        second_events,
        universe_id=inputs["candidate_pool"]["universe_id"],
        data_cutoff=inputs["candidate_pool"]["data_cutoff"],
        frozen_at=inputs["candidate_pool"]["frozen_at"],
        membership_as_of=inputs["session_clock"]["assignment_cutoff"],
    )
    clock = deepcopy(inputs["market_clock_snapshot"])
    clock["memberships"] = alternate_memberships
    clock = _reseal_market_clock_memberships(clock)
    inputs["market_clock_snapshot"] = clock
    inputs["expected_market_clock_snapshot_hash"] = clock[
        "market_decision_clock_snapshot_hash"
    ]

    class ChangingEvents(Sequence):
        def __init__(self, first, second):
            self.first = first
            self.second = second
            self.iteration_count = 0

        def __len__(self):
            return len(self.first)

        def __getitem__(self, index):
            return self.first[index]

        def __iter__(self):
            self.iteration_count += 1
            rows = self.first if self.iteration_count == 1 else self.second
            return iter(rows)

    changing_events = ChangingEvents(first_events, second_events)
    inputs["universe_events"] = changing_events

    _assert_code(
        "dynamic_market_universe_membership_lineage_mismatch",
        lambda: _build(inputs),
    )
    assert changing_events.iteration_count == 1


def test_builder_freezes_expected_research_identity_before_other_inputs():
    inputs = _inputs_with_quarantine_membership()
    expected_identity_b = deepcopy(inputs["expected_research_input_identity"])
    shared_expected_identity = deepcopy(
        _inputs()["expected_research_input_identity"]
    )
    inputs["expected_research_input_identity"] = shared_expected_identity

    class MutatingClaims(Sequence):
        def __init__(self, claims):
            self.claims = claims
            self.iteration_count = 0

        def __len__(self):
            return len(self.claims)

        def __getitem__(self, index):
            return self.claims[index]

        def __iter__(self):
            self.iteration_count += 1
            shared_expected_identity.clear()
            shared_expected_identity.update(expected_identity_b)
            return iter(self.claims)

    mutating_claims = MutatingClaims(deepcopy(inputs["research_claims"]))
    inputs["research_claims"] = mutating_claims

    _assert_code(
        "dynamic_market_universe_frozen_research_identity_mismatch",
        lambda: _build(inputs),
    )
    assert mutating_claims.iteration_count == 1


def test_validator_freezes_expected_research_identity_before_snapshot():
    inputs = _inputs_with_quarantine_membership()
    expected_identity_b = deepcopy(inputs["expected_research_input_identity"])
    shared_expected_identity = deepcopy(
        _inputs()["expected_research_input_identity"]
    )
    inputs["expected_research_input_identity"] = shared_expected_identity

    class MutatingSnapshot(Mapping):
        def __init__(self, snapshot):
            self.snapshot = snapshot

        def __len__(self):
            return len(self.snapshot)

        def __getitem__(self, key):
            return self.snapshot[key]

        def __iter__(self):
            shared_expected_identity.clear()
            shared_expected_identity.update(expected_identity_b)
            return iter(self.snapshot)

    inputs["dynamic_market_universe_snapshot"] = MutatingSnapshot(
        deepcopy(inputs["dynamic_market_universe_snapshot"])
    )

    _assert_code(
        "dynamic_market_universe_frozen_research_identity_mismatch",
        lambda: _validate(inputs),
    )


def test_validator_returns_dependency_reconstructed_plain_snapshot():
    inputs = _inputs()
    original_lineage = deepcopy(
        inputs["dynamic_market_universe_snapshot"]["membership_lineage"]
    )

    class CallerLineage(Mapping):
        def __len__(self):
            return len(original_lineage)

        def __getitem__(self, key):
            return original_lineage[key]

        def __iter__(self):
            return iter(original_lineage)

        def __deepcopy__(self, memo):
            return self

    inputs["dynamic_market_universe_snapshot"] = deepcopy(
        inputs["dynamic_market_universe_snapshot"]
    )
    inputs["dynamic_market_universe_snapshot"]["membership_lineage"] = (
        CallerLineage()
    )

    validated = _validate(inputs)

    assert type(validated["membership_lineage"]) is dict
    assert validated["membership_lineage"] == original_lineage
