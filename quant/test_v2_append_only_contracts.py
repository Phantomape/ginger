from copy import deepcopy

import pytest

from quant.test_v2_contracts import _assert_code, _event, _seal_event
from quant.test_v2_decision_outcome_contracts import (
    _chain,
    _outcome,
    _replacement,
    _seal,
)
from quant.v2_contracts import validate_append_only_append


def test_universe_event_append_and_recorded_at_retry_are_idempotent():
    event = _event()

    assert validate_append_only_append([], event) == "append"
    assert validate_append_only_append([event], event) == "duplicate"

    retry = deepcopy(event)
    retry["recorded_at"] = "2026-08-20T14:05:30Z"
    retry = _seal_event(retry)
    assert retry["semantic_hash"] == event["semantic_hash"]
    assert retry["event_hash"] != event["event_hash"]
    assert validate_append_only_append([event], retry) == "duplicate"


def test_universe_event_id_semantic_drift_fails_closed():
    event = _event()
    conflict = deepcopy(event)
    conflict["reason"] = "Changed after the universe event was frozen."
    conflict = _seal_event(conflict)

    _assert_code(
        "immutable_key_conflict",
        lambda: validate_append_only_append([event], conflict),
    )


@pytest.mark.parametrize("kind", ("decision", "intent"))
def test_immutable_records_append_once_and_retry_by_semantics(kind):
    _, decision, intent, *_ = _chain()
    row = decision if kind == "decision" else intent

    assert validate_append_only_append([], row) == "append"
    assert validate_append_only_append([row], row) == "duplicate"

    retry = deepcopy(row)
    retry["recorded_at"] = retry["recorded_at"].replace(":00Z", ":30Z")
    retry = _seal(
        retry,
        nested_sort=("items", "candidate_entry_id") if kind == "decision" else None,
    )
    assert retry["semantic_hash"] == row["semantic_hash"]
    assert retry["record_hash"] != row["record_hash"]
    assert validate_append_only_append([row], retry) == "duplicate"


@pytest.mark.parametrize("kind", ("decision", "intent"))
def test_immutable_same_key_semantic_drift_fails_closed(kind):
    _, decision, intent, *_ = _chain()
    row = decision if kind == "decision" else intent
    conflict = deepcopy(row)
    if kind == "decision":
        conflict["items"][0]["reason"] = "Changed after the decision was frozen."
        conflict = _seal(conflict, nested_sort=("items", "candidate_entry_id"))
    else:
        conflict["time_in_force"] = "gtc"
        conflict = _seal(conflict)

    _assert_code(
        "immutable_key_conflict",
        lambda: validate_append_only_append([row], conflict),
    )


def _second_outcome(decision, intent, evidence, first):
    return _outcome(
        decision,
        intent,
        evidence,
        outcome_id="outcome-intent-20260820-r2",
        revision_number=2,
        previous_outcome_id=first["outcome_id"],
        previous_outcome_record_hash=first["record_hash"],
        settled_at="2026-08-20T15:40:00Z",
        recorded_at="2026-08-20T15:41:00Z",
    )


def test_outcome_append_duplicate_and_exact_correction_chain():
    _, decision, intent, evidence, first, *_ = _chain()
    second = _second_outcome(decision, intent, evidence, first)

    assert validate_append_only_append([], first) == "append"
    assert validate_append_only_append([first], first) == "duplicate"
    assert validate_append_only_append([first], second) == "correction"
    assert validate_append_only_append([first, second], second) == "duplicate"


@pytest.mark.parametrize(
    ("mutation", "code"),
    (
        ("gap", "revision_gap"),
        ("wrong_predecessor", "previous_outcome_binding_mismatch"),
        ("reused_id", "physical_id_reused"),
        ("stale_fork", "stale_revision_fork"),
    ),
)
def test_outcome_correction_gaps_forks_and_id_reuse_fail_closed(mutation, code):
    _, decision, intent, evidence, first, *_ = _chain()
    second = _second_outcome(decision, intent, evidence, first)
    proposed = _second_outcome(decision, intent, evidence, first)
    existing = [first]

    if mutation == "gap":
        proposed["outcome_id"] = "outcome-intent-20260820-r3"
        proposed["revision_number"] = 3
    elif mutation == "wrong_predecessor":
        proposed["previous_outcome_record_hash"] = "0" * 64
    elif mutation == "reused_id":
        proposed["outcome_id"] = first["outcome_id"]
    else:
        existing.append(second)
        proposed["outcome_id"] = "outcome-intent-20260820-r2-fork"
        proposed["reason"] = "Conflicting correction from a stale predecessor."
    proposed = _seal(proposed, list_fields=("settlement_evidence_record_ids",))

    _assert_code(code, lambda: validate_append_only_append(existing, proposed))


def test_existing_outcome_population_rejects_missing_initial_revision_and_duplicates():
    _, decision, intent, evidence, first, *_ = _chain()
    second = _second_outcome(decision, intent, evidence, first)

    _assert_code(
        "existing_revision_gap",
        lambda: validate_append_only_append([second], first),
    )
    _assert_code(
        "existing_physical_id_reused",
        lambda: validate_append_only_append([first, deepcopy(first)], first),
    )


def _second_replacement(second_outcome, pool, evidence, first):
    return _replacement(
        second_outcome,
        pool,
        [evidence],
        first["comparator_role"],
        previous_replacement_value_id=first["replacement_value_id"],
        previous_replacement_value_record_hash=first["record_hash"],
        settled_at="2026-08-20T15:42:00Z",
        recorded_at="2026-08-20T15:43:00Z",
    )


def test_replacement_append_duplicate_and_exact_correction_chain():
    (
        graph,
        decision,
        intent,
        settlement_evidence,
        first_outcome,
        comparator_evidence,
        rows,
    ) = _chain()
    second_outcome = _second_outcome(
        decision, intent, settlement_evidence, first_outcome
    )
    first = rows[0]
    second = _second_replacement(
        second_outcome, graph["pool"], comparator_evidence[0], first
    )

    assert validate_append_only_append([], first) == "append"
    assert validate_append_only_append([first], first) == "duplicate"
    assert validate_append_only_append([first], second) == "correction"
    assert validate_append_only_append([first, second], second) == "duplicate"


@pytest.mark.parametrize(
    ("mutation", "code"),
    (
        ("gap", "revision_gap"),
        ("wrong_predecessor", "previous_replacement_binding_mismatch"),
        ("reused_id", "physical_id_reused"),
        ("stale_fork", "stale_revision_fork"),
    ),
)
def test_replacement_correction_gaps_forks_and_id_reuse_fail_closed(mutation, code):
    (
        graph,
        decision,
        intent,
        settlement_evidence,
        first_outcome,
        comparator_evidence,
        rows,
    ) = _chain()
    second_outcome = _second_outcome(
        decision, intent, settlement_evidence, first_outcome
    )
    first = rows[0]
    second = _second_replacement(
        second_outcome, graph["pool"], comparator_evidence[0], first
    )
    proposed = deepcopy(second)
    existing = [first]

    if mutation == "gap":
        proposed["replacement_value_id"] = "replacement-cash-r3"
        proposed["revision_number"] = 3
    elif mutation == "wrong_predecessor":
        proposed["previous_replacement_value_record_hash"] = "0" * 64
    elif mutation == "reused_id":
        proposed["replacement_value_id"] = first["replacement_value_id"]
    else:
        existing.append(second)
        proposed["replacement_value_id"] = "replacement-cash-r2-fork"
        proposed["reason"] = "Conflicting comparator correction from a stale row."
    proposed = _seal(proposed, list_fields=("comparator_evidence_record_ids",))

    _assert_code(code, lambda: validate_append_only_append(existing, proposed))
