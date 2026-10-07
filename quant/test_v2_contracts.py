from copy import deepcopy
from dataclasses import replace

import pytest

from quant.v2_contracts import (
    EvidenceRecord,
    SecurityMappingSnapshot,
    SourceContract,
    UniverseEvent,
    V2ContractValidationError,
    canonical_hash,
    normalize_evidence_record,
    normalize_source_contract,
    normalize_universe_event,
    universe_input_snapshot_hash,
    validate_evidence_against_source,
    validate_evidence_record,
    validate_source_contract,
    validate_universe_event,
    validate_universe_event_against_evidence,
)


def _seal_mapping(row):
    row = deepcopy(row)
    row.pop("mapping_sha256", None)
    row["mapping_sha256"] = canonical_hash(row)
    return row


def _mapping(**overrides):
    row = {
        "mapping_id": "map-sec-aaa-xnas-v1",
        "security_id": "sec-aaa",
        "listing_id": "listing-aaa-xnas",
        "symbol": "AAA",
        "mic": "XNAS",
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "known_at": "2020-01-01T00:00:00Z",
        "source_snapshot_sha256": "a" * 64,
    }
    row.update(overrides)
    return _seal_mapping(row)


def _seal_source(row):
    row = deepcopy(row)
    for field in ("raw_identity_fields", "decision_content_fields", "permitted_uses"):
        if field in row:
            row[field] = sorted(row[field])
    row.pop("source_contract_hash", None)
    row["source_contract_hash"] = canonical_hash(row)
    return row


def _source(**overrides):
    row = {
        "schema_version": 1,
        "record_type": "v2_source_contract",
        "source_contract_id": "source-official-events-v1",
        "contract_version": "1",
        "provider": "Official Agency",
        "source_name": "official_event_feed",
        "source_kind": "official",
        "source_locator": "https://agency.example/events",
        "raw_identity_fields": ["event_id", "revision_id"],
        "decision_content_fields": ["event_state", "published_at"],
        "authorization_status": "pass",
        "authorization_reference": "terms-snapshot-20260819",
        "authorization_evidence_sha256": "b" * 64,
        "permitted_uses": ["research"],
        "availability_status": "pass",
        "availability_reference": "availability-audit-20260819",
        "source_timezone": "America/New_York",
        "observed_at_rule": "local receipt timestamp",
        "published_at_rule": "publisher timestamp",
        "published_at_field": "published_at",
        "known_at_rule": "max(observed_at,published_at)",
        "decision_calendar": "XNYS",
        "session_assignment_rule": "next open session after known_at",
        "revision_policy": "versioned",
        "revision_id_field": "revision_id",
        "security_mapping_policy": "effective_dated",
        "normalizer_id": "official-event-normalizer",
        "normalizer_version": "1",
        "adjustment_policy": "as_published_no_future_adjustment",
        "replay_daily_parity_status": "unknown",
        "maximum_pit_tier": "research_pit",
        "known_future_leakage": False,
        "effective_from": "2026-08-20T00:00:00Z",
        "effective_to": None,
        "created_at": "2026-08-19T23:00:00Z",
        "trade_enabled": False,
    }
    row.update(overrides)
    return _seal_source(row)


def _seal_evidence(row, *, bind_content=True):
    row = deepcopy(row)
    if bind_content:
        row["decision_content_sha256"] = canonical_hash(row["decision_content"])
    row.pop("semantic_hash", None)
    row.pop("record_hash", None)
    semantic = deepcopy(row)
    semantic.pop("recorded_at")
    row["semantic_hash"] = canonical_hash(semantic)
    record = deepcopy(row)
    row["record_hash"] = canonical_hash(record)
    return row


def _evidence(*, source=None, **overrides):
    source = _source() if source is None else source
    row = {
        "schema_version": 1,
        "record_type": "v2_evidence_record",
        "evidence_id": "evidence-official-event-1-r1",
        "source_contract_id": source["source_contract_id"],
        "source_contract_hash": source["source_contract_hash"],
        "raw_identity": {"event_id": "event-1", "revision_id": "r1"},
        "raw_artifact_locator": "raw/official/event-1-r1.json",
        "raw_artifact_sha256": "c" * 64,
        "decision_content": {
            "event_state": "confirmed",
            "published_at": "2026-08-20T14:00:00Z",
        },
        "decision_content_sha256": "0" * 64,
        "normalizer_id": source["normalizer_id"],
        "normalizer_version": source["normalizer_version"],
        "source_timezone": source["source_timezone"],
        "observed_at": "2026-08-20T14:02:00Z",
        "published_at": "2026-08-20T14:00:00Z",
        "known_at": "2026-08-20T14:02:00Z",
        "known_at_basis": "max(observed_at,published_at)",
        "effective_from": "2026-08-20T14:00:00Z",
        "effective_to": None,
        "revision_id": "r1",
        "supersedes_evidence_id": None,
        "security_scope": "instrument",
        "security_mapping_kind": "effective_dated",
        "security_mapping": _mapping(),
        "authorization_status": source["authorization_status"],
        "authorization_evidence_sha256": source["authorization_evidence_sha256"],
        "pit_tier": "research_pit",
        "known_future_leakage": False,
        "recorded_at": "2026-08-20T14:03:00Z",
        "trade_enabled": False,
        "semantic_hash": "0" * 64,
        "record_hash": "0" * 64,
    }
    row.update(overrides)
    return _seal_evidence(row)


def _seal_event(row):
    row = deepcopy(row)
    row.pop("semantic_hash", None)
    row.pop("event_hash", None)
    semantic = deepcopy(row)
    semantic.pop("recorded_at")
    row["semantic_hash"] = canonical_hash(semantic)
    record = deepcopy(row)
    row["event_hash"] = canonical_hash(record)
    return row


def _event(*, evidence=None, **overrides):
    evidence = _evidence() if evidence is None else evidence
    mapping = _mapping()
    rule_sha256 = "d" * 64
    row = {
        "schema_version": 2,
        "record_type": "v2_universe_event",
        "event_id": "universe-event-aaa-discovery-1",
        "event_batch_id": "universe-batch-20260820-1",
        "universe_id": "v2-research-universe",
        "event_type": "discovery",
        "from_state": None,
        "to_state": "discovered",
        "security_mapping": mapping,
        "reason_code": "source_discovery",
        "reason": "First PIT-qualified observation for the security.",
        "rule_id": "universe-discovery-rule",
        "rule_version": "1",
        "rule_sha256": rule_sha256,
        "evidence_record_ids": [evidence["evidence_id"]],
        "input_snapshot_sha256": universe_input_snapshot_hash(
            [evidence],
            rule_sha256=rule_sha256,
            security_mapping_sha256=mapping["mapping_sha256"],
            session_clock_id="clock-v2-run-20260820",
            session_clock_hash="f" * 64,
            session_clock_record_hash="e" * 64,
            effective_session_clock_id="clock-v2-run-20260820",
            effective_session_clock_hash="f" * 64,
            effective_session_clock_record_hash="e" * 64,
        ),
        "pit_tier": "research_pit",
        "known_future_leakage": False,
        "run_id": "v2-universe-run-20260820-1",
        "session_clock_id": "clock-v2-run-20260820",
        "session_clock_hash": "f" * 64,
        "session_clock_record_hash": "e" * 64,
        "run_date": "2026-08-20",
        "calendar_session_id": "XNYS-2026-08-20",
        "known_at": "2026-08-20T14:02:00Z",
        "decided_at": "2026-08-20T14:04:00Z",
        "recorded_at": "2026-08-20T14:05:00Z",
        "effective_at": "2026-08-20T14:06:00Z",
        "effective_session_id": "XNYS-2026-08-20",
        "effective_session_clock_id": "clock-v2-run-20260820",
        "effective_session_clock_hash": "f" * 64,
        "effective_session_clock_record_hash": "e" * 64,
        "previous_event_id": None,
        "previous_event_hash": None,
        "trade_enabled": False,
        "semantic_hash": "0" * 64,
        "event_hash": "0" * 64,
    }
    row.update(overrides)
    return _seal_event(row)


def _assert_code(code, func):
    with pytest.raises(V2ContractValidationError) as caught:
        func()
    assert caught.value.code == code
    assert caught.value.to_dict()["code"] == code


def test_source_contract_round_trip_hash_and_normalization_are_stable():
    row = _source(
        raw_identity_fields=["revision_id", "event_id"],
        permitted_uses=["research", "internal_analysis"],
    )
    original = deepcopy(row)
    contract = validate_source_contract(row)

    assert isinstance(contract, SourceContract)
    assert row == original
    assert contract.raw_identity_fields == ("event_id", "revision_id")
    assert normalize_source_contract(contract) == normalize_source_contract(row)
    assert contract.canonical_hash == canonical_hash(contract.to_dict())


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (lambda row: row.pop("known_at_rule"), "missing_field"),
        (lambda row: row.update(extra="nope"), "unknown_field"),
        (lambda row: row.update(schema_version=True), "integer_required"),
        (lambda row: row.update(trade_enabled=True), "trade_enabled_forbidden"),
        (lambda row: row.update(created_at="2026-08-19"), "instant_required"),
        (
            lambda row: row.update(created_at="2026-08-19T23:00:00"),
            "timezone_required",
        ),
    ],
)
def test_source_contract_fails_closed_on_shape_clock_and_default_off(mutator, code):
    row = _source()
    mutator(row)
    row = _seal_source(row)
    _assert_code(code, lambda: validate_source_contract(row))


def test_source_contract_hash_tamper_is_rejected():
    row = _source()
    row["source_name"] = "tampered"
    _assert_code("hash_mismatch", lambda: validate_source_contract(row))


def test_dataclass_instances_are_revalidated_not_trusted():
    source = validate_source_contract(_source())
    evidence = validate_evidence_record(_evidence())
    event = validate_universe_event(_event())

    _assert_code(
        "trade_enabled_forbidden",
        lambda: validate_source_contract(replace(source, trade_enabled=True)),
    )
    _assert_code(
        "trade_enabled_forbidden",
        lambda: validate_evidence_record(replace(evidence, trade_enabled=True)),
    )
    _assert_code(
        "trade_enabled_forbidden",
        lambda: validate_universe_event(replace(event, trade_enabled=True)),
    )
    _assert_code(
        "hash_mismatch",
        lambda: validate_source_contract(replace(source, provider="tampered")),
    )


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        (
            {"authorization_status": "unknown", "authorization_evidence_sha256": None},
            "authorization_not_verified",
        ),
        ({"availability_status": "fail"}, "availability_not_verified"),
        ({"known_future_leakage": True}, "future_leakage_requires_not_pit"),
        ({"security_mapping_policy": "current_only"}, "current_mapping_requires_not_pit"),
    ],
)
def test_research_source_requires_authority_pit_mapping_and_forward_start(overrides, code):
    _assert_code(code, lambda: validate_source_contract(_source(**overrides)))


def test_canonical_source_requires_revision_and_parity_contracts():
    _assert_code(
        "canonical_parity_required",
        lambda: validate_source_contract(_source(maximum_pit_tier="canonical_pit")),
    )


def test_source_clock_and_revision_field_paths_must_be_declared():
    _assert_code(
        "published_field_not_declared",
        lambda: validate_source_contract(_source(published_at_field="missing_clock")),
    )
    _assert_code(
        "revision_field_not_declared",
        lambda: validate_source_contract(_source(revision_id_field="missing_revision")),
    )


def test_historical_research_contract_is_allowed_but_canonical_cannot_be_backdated():
    research = _source(effective_from="2026-01-01T00:00:00Z")
    assert validate_source_contract(research).maximum_pit_tier == "research_pit"

    canonical = _source(
        maximum_pit_tier="canonical_pit",
        replay_daily_parity_status="pass",
        effective_from="2026-01-01T00:00:00Z",
    )
    _assert_code(
        "retroactive_contract_start", lambda: validate_source_contract(canonical)
    )
    _assert_code(
        "canonical_revision_policy_required",
        lambda: validate_source_contract(
            _source(
                maximum_pit_tier="canonical_pit",
                replay_daily_parity_status="pass",
                revision_policy="mutable_current",
            )
        ),
    )


def test_security_mapping_is_hash_bound_and_half_open():
    mapping = SecurityMappingSnapshot.from_dict(
        _mapping(effective_to="2026-08-21T00:00:00Z")
    )
    assert mapping.covers("2026-08-20T23:59:59Z")
    assert not mapping.covers("2026-08-21T00:00:00Z")
    tampered = mapping.to_dict()
    tampered["symbol"] = "BBB"
    _assert_code("hash_mismatch", lambda: SecurityMappingSnapshot.from_dict(tampered))


def test_evidence_round_trip_content_hash_and_nested_values_are_immutable():
    source = _source()
    row = _evidence(source=source)
    original = deepcopy(row)
    record = validate_evidence_against_source(row, source)

    assert isinstance(record, EvidenceRecord)
    assert row == original
    assert normalize_evidence_record(record) == normalize_evidence_record(row)
    with pytest.raises(TypeError):
        record.decision_content["event_state"] = "changed"
    with pytest.raises(AttributeError):
        record.security_mapping.symbol = "BBB"


def test_evidence_decision_content_and_record_hashes_reject_tamper():
    content_tamper = _evidence()
    content_tamper["decision_content"]["event_state"] = "revised"
    _assert_code(
        "decision_content_hash_mismatch",
        lambda: validate_evidence_record(content_tamper),
    )

    record_tamper = _evidence()
    record_tamper["raw_artifact_locator"] = "raw/tampered.json"
    _assert_code("semantic_hash_mismatch", lambda: validate_evidence_record(record_tamper))


@pytest.mark.parametrize(
    "field",
    ["known_at", "raw_artifact_sha256", "authorization_status", "semantic_hash"],
)
def test_evidence_rejects_missing_clock_hash_and_authorization_fields(field):
    row = _evidence()
    row.pop(field)
    _assert_code("missing_field", lambda: validate_evidence_record(row))


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"observed_at": "2026-08-20T14:03:00Z"}, "known_at_before_source_clock"),
        ({"published_at": "2026-08-20T14:03:00Z"}, "known_at_before_source_clock"),
        ({"known_at": "2026-08-20"}, "instant_required"),
        ({"known_at": "2026-08-20T14:02:00"}, "timezone_required"),
        ({"recorded_at": "2026-08-20T14:01:00Z"}, "recorded_before_known"),
        ({"trade_enabled": True}, "trade_enabled_forbidden"),
        ({"known_future_leakage": True}, "future_leakage_requires_not_pit"),
    ],
)
def test_evidence_fails_closed_on_clock_leakage_and_default_off(overrides, code):
    _assert_code(code, lambda: validate_evidence_record(_evidence(**overrides)))


def test_current_mapping_cannot_be_backfilled_into_pit_evidence():
    row = _evidence(security_mapping_kind="current_only", security_mapping=None)
    _assert_code("current_mapping_requires_not_pit", lambda: validate_evidence_record(row))


def test_evidence_mapping_must_be_known_and_effective_at_known_at():
    late = _evidence(security_mapping=_mapping(known_at="2026-08-20T14:03:00Z"))
    _assert_code("mapping_known_too_late", lambda: validate_evidence_record(late))

    expired = _evidence(
        security_mapping=_mapping(effective_to="2026-08-20T14:02:00Z")
    )
    _assert_code("mapping_interval_miss", lambda: validate_evidence_record(expired))


def test_evidence_source_binding_rejects_hash_tier_normalizer_and_interval_drift():
    source = _source()
    wrong_hash = _evidence(source_contract_hash="e" * 64)
    _assert_code(
        "source_contract_hash_mismatch",
        lambda: validate_evidence_against_source(wrong_hash, source),
    )

    canonical = _evidence(source=source, pit_tier="canonical_pit")
    _assert_code(
        "pit_tier_exceeds_source",
        lambda: validate_evidence_against_source(canonical, source),
    )

    wrong_normalizer = _evidence(source=source, normalizer_version="2")
    _assert_code(
        "normalizer_mismatch",
        lambda: validate_evidence_against_source(wrong_normalizer, source),
    )

    expired_source = _source(effective_to="2026-08-20T13:00:00Z")
    expired_evidence = _evidence(source=expired_source)
    _assert_code(
        "source_contract_interval_miss",
        lambda: validate_evidence_against_source(expired_evidence, expired_source),
    )

    late_contract = _source(
        effective_from="2026-01-01T00:00:00Z",
        created_at="2026-08-20T14:10:00Z",
    )
    pre_contract_record = _evidence(source=late_contract)
    _assert_code(
        "evidence_recorded_before_contract",
        lambda: validate_evidence_against_source(pre_contract_record, late_contract),
    )


@pytest.mark.parametrize(
    ("field", "mutation", "code"),
    [
        (
            "decision_content",
            lambda value: {**value, "future_return": 0.99},
            "decision_content_fields_mismatch",
        ),
        (
            "decision_content",
            lambda value: {"event_state": value["event_state"]},
            "decision_content_fields_mismatch",
        ),
        (
            "raw_identity",
            lambda value: {**value, "current_symbol": "AAA"},
            "raw_identity_fields_mismatch",
        ),
        (
            "raw_identity",
            lambda value: {"event_id": value["event_id"]},
            "raw_identity_fields_mismatch",
        ),
    ],
)
def test_evidence_fields_must_exactly_match_source_declarations(field, mutation, code):
    source = _source()
    row = _evidence(source=source)
    row[field] = mutation(row[field])
    row = _seal_evidence(row)
    _assert_code(code, lambda: validate_evidence_against_source(row, source))


def test_evidence_clock_and_revision_values_must_match_source_declared_fields():
    source = _source()
    future_clock = _evidence(source=source)
    future_clock["decision_content"]["published_at"] = "2099-01-01T00:00:00Z"
    future_clock = _seal_evidence(future_clock)
    _assert_code(
        "published_at_mismatch",
        lambda: validate_evidence_against_source(future_clock, source),
    )

    wrong_revision = _evidence(source=source)
    wrong_revision["raw_identity"]["revision_id"] = "r2"
    wrong_revision = _seal_evidence(wrong_revision)
    _assert_code(
        "revision_id_mismatch",
        lambda: validate_evidence_against_source(wrong_revision, source),
    )

    observed_only_source = _source(published_at_field=None)
    observed_only_record = _evidence(source=observed_only_source)
    _assert_code(
        "published_at_not_declared",
        lambda: validate_evidence_against_source(
            observed_only_record, observed_only_source
        ),
    )


def test_universe_event_round_trip_binds_frozen_clock_mapping_and_evidence():
    source = _source()
    evidence = _evidence(source=source)
    row = _event(evidence=evidence)
    original = deepcopy(row)
    event = validate_universe_event_against_evidence(row, [evidence], [source])

    assert isinstance(event, UniverseEvent)
    assert row == original
    assert normalize_universe_event(event) == normalize_universe_event(row)
    assert event.to_state == "discovered"
    assert event.trade_enabled is False


def test_universe_input_snapshot_binds_evidence_recorded_at_for_causality():
    evidence = _evidence()
    later_record = deepcopy(evidence)
    later_record["recorded_at"] = "2026-08-20T14:04:00Z"
    later_record = _seal_evidence(later_record)
    assert evidence["semantic_hash"] == later_record["semantic_hash"]
    assert evidence["record_hash"] != later_record["record_hash"]
    assert universe_input_snapshot_hash(
        [evidence],
        rule_sha256="d" * 64,
        security_mapping_sha256=evidence["security_mapping"]["mapping_sha256"],
        session_clock_id="clock-v2-run-20260820",
        session_clock_hash="f" * 64,
        session_clock_record_hash="e" * 64,
        effective_session_clock_id="clock-v2-run-20260820",
        effective_session_clock_hash="f" * 64,
        effective_session_clock_record_hash="e" * 64,
    ) != universe_input_snapshot_hash(
        [later_record],
        rule_sha256="d" * 64,
        security_mapping_sha256=later_record["security_mapping"]["mapping_sha256"],
        session_clock_id="clock-v2-run-20260820",
        session_clock_hash="f" * 64,
        session_clock_record_hash="e" * 64,
        effective_session_clock_id="clock-v2-run-20260820",
        effective_session_clock_hash="f" * 64,
        effective_session_clock_record_hash="e" * 64,
    )


def test_evidence_recorded_at_cannot_be_backdated_without_rebinding_event():
    source = _source()
    late = _evidence(source=source, recorded_at="2026-08-20T14:05:00Z")
    event = _event(evidence=late)
    _assert_code(
        "evidence_recorded_after_decision",
        lambda: validate_universe_event_against_evidence(event, [late], [source]),
    )

    backdated = deepcopy(late)
    backdated["recorded_at"] = "2026-08-20T14:03:00Z"
    backdated = _seal_evidence(backdated)
    assert backdated["semantic_hash"] == late["semantic_hash"]
    assert backdated["record_hash"] != late["record_hash"]
    _assert_code(
        "input_snapshot_hash_mismatch",
        lambda: validate_universe_event_against_evidence(
            event, [backdated], [source]
        ),
    )


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"calendar_session_id": ""}, "empty_string"),
        ({"run_date": "2026-8-20"}, "invalid_date"),
        ({"known_at": "2026-08-20"}, "instant_required"),
        ({"recorded_at": "2026-08-20T14:03:00Z"}, "invalid_event_chronology"),
        ({"trade_enabled": True}, "trade_enabled_forbidden"),
        ({"known_future_leakage": True}, "future_leakage_requires_not_pit"),
    ],
)
def test_universe_event_fails_closed_on_frozen_clock_and_default_off(overrides, code):
    _assert_code(code, lambda: validate_universe_event(_event(**overrides)))


@pytest.mark.parametrize(
    "field",
    ["run_date", "calendar_session_id", "input_snapshot_sha256", "security_mapping"],
)
def test_universe_event_rejects_missing_clock_snapshot_and_mapping_fields(field):
    row = _event()
    row.pop(field)
    _assert_code("missing_field", lambda: validate_universe_event(row))


def test_universe_discovery_and_transition_chain_are_strict():
    bad_discovery = _event(from_state="research_eligible")
    _assert_code(
        "invalid_discovery_transition", lambda: validate_universe_event(bad_discovery)
    )

    missing_previous = _event(
        event_type="state_transition",
        from_state="discovered",
        to_state="research_eligible",
    )
    _assert_code("previous_event_required", lambda: validate_universe_event(missing_previous))

    retired = _event(
        event_type="state_transition",
        from_state="retired",
        to_state="research_eligible",
        previous_event_id="event-prior",
        previous_event_hash="f" * 64,
    )
    _assert_code("invalid_universe_transition", lambda: validate_universe_event(retired))


def test_universe_mapping_must_be_known_and_cover_effective_time():
    late = _event(security_mapping=_mapping(known_at="2026-08-20T14:03:00Z"))
    _assert_code("mapping_known_too_late", lambda: validate_universe_event(late))

    expired = _event(
        security_mapping=_mapping(effective_to="2026-08-20T14:06:00Z")
    )
    _assert_code("mapping_interval_miss", lambda: validate_universe_event(expired))


def test_universe_evidence_link_rejects_missing_tier_escalation_and_snapshot_tamper():
    source = _source()
    evidence = _evidence(source=source)
    event = _event(evidence=evidence)
    _assert_code(
        "unresolved_evidence_id",
        lambda: validate_universe_event_against_evidence(event, [], [source]),
    )

    not_pit_evidence = _evidence(
        source=source,
        pit_tier="not_pit",
    )
    escalated = _event(evidence=not_pit_evidence, pit_tier="research_pit")
    _assert_code(
        "pit_tier_exceeds_evidence",
        lambda: validate_universe_event_against_evidence(
            escalated, [not_pit_evidence], [source]
        ),
    )

    tampered = deepcopy(event)
    tampered["input_snapshot_sha256"] = "1" * 64
    tampered = _seal_event(tampered)
    _assert_code(
        "input_snapshot_hash_mismatch",
        lambda: validate_universe_event_against_evidence(
            tampered, [evidence], [source]
        ),
    )

    future_record = _evidence(
        source=source, recorded_at="2026-08-20T14:05:00Z"
    )
    future_event = _event(evidence=future_record)
    _assert_code(
        "evidence_recorded_after_decision",
        lambda: validate_universe_event_against_evidence(
            future_event, [future_record], [source]
        ),
    )


def test_universe_evidence_security_identity_cannot_use_symbol_only():
    source = _source()
    evidence = _evidence(
        source=source,
        security_mapping=_mapping(security_id="sec-bbb", symbol="AAA"),
    )
    event = _event(evidence=evidence)
    _assert_code(
        "evidence_security_mapping_mismatch",
        lambda: validate_universe_event_against_evidence(event, [evidence], [source]),
    )


def test_universe_evidence_must_bind_exact_listing_mapping_for_same_security():
    source = _source()
    evidence = _evidence(
        source=source,
        security_mapping=_mapping(
            mapping_id="map-sec-aaa-xnys-v2",
            listing_id="listing-aaa-xnys",
            symbol="AAA.B",
            mic="XNYS",
        ),
    )
    event = _event(evidence=evidence)
    _assert_code(
        "evidence_security_mapping_mismatch",
        lambda: validate_universe_event_against_evidence(event, [evidence], [source]),
    )


def test_universe_event_rejects_global_evidence_without_mapping_evidence():
    source = _source(security_mapping_policy="not_applicable")
    evidence = _evidence(
        source=source,
        security_scope="not_applicable",
        security_mapping_kind="not_applicable",
        security_mapping=None,
    )
    event = _event(evidence=evidence)
    _assert_code(
        "event_mapping_evidence_required",
        lambda: validate_universe_event_against_evidence(event, [evidence], [source]),
    )


def test_universe_event_requires_real_source_contracts_for_every_evidence_record():
    source = _source()
    missing_source_evidence = _evidence(
        source_contract_id="source-does-not-exist",
        source_contract_hash="e" * 64,
        pit_tier="canonical_pit",
    )
    missing_source_event = _event(
        evidence=missing_source_evidence, pit_tier="canonical_pit"
    )
    _assert_code(
        "unresolved_source_contract_id",
        lambda: validate_universe_event_against_evidence(
            missing_source_event, [missing_source_evidence], [source]
        ),
    )

    tier_overclaim = _evidence(source=source, pit_tier="canonical_pit")
    tier_overclaim_event = _event(evidence=tier_overclaim, pit_tier="canonical_pit")
    _assert_code(
        "pit_tier_exceeds_source",
        lambda: validate_universe_event_against_evidence(
            tier_overclaim_event, [tier_overclaim], [source]
        ),
    )
