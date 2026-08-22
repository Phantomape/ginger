from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from quant.test_v2_contracts import _event, _evidence, _seal_event, _source
from quant.test_v2_decision_outcome_contracts import _decision, _intent
from quant.test_v2_research_contracts import _graph, _seal_pool
from quant.v2_contracts import (
    CLOCK_BOUND_SCHEMA_VERSION,
    CalendarSession,
    CandidatePool,
    DecisionRecord,
    OrderIntent,
    SessionClock,
    UniverseEvent,
    V2ContractValidationError,
    calendar_session_snapshot_hash,
    calendar_session_snapshot_payload,
    candidate_pool_input_snapshot_hash,
    canonical_hash,
    normalize_session_clock,
    universe_input_snapshot_hash,
    validate_append_only_append,
    validate_candidate_pool,
    validate_decision_record,
    validate_decision_record_against_candidate_pool,
    validate_evidence_against_source,
    validate_order_intent,
    validate_order_intent_against_decision,
    validate_record_against_session_clock,
    validate_session_clock,
    validate_session_clock_against_calendar,
    validate_universe_event_against_session_clocks,
    validate_universe_event,
)


CALENDAR_ID = "XNYS"
CALENDAR_VERSION = "2026.08.20-v1"
CALENDAR_TIMEZONE = "America/New_York"
GOLDEN_CALENDAR_HASH = (
    "b9776977234b8861aa53ba9fe52432c54cb5f55b71ba3715cc0650b92f7ca78e"
)


def _session(
    session_date,
    open_at,
    close_at,
    *,
    session_kind="regular",
    calendar_session_id=None,
):
    return {
        "calendar_session_id": calendar_session_id
        or f"{CALENDAR_ID}-{session_date}",
        "session_date": session_date,
        "open_at": open_at,
        "close_at": close_at,
        "session_kind": session_kind,
    }


def _regular_sessions():
    return [
        _session("2026-08-20", "2026-08-20T13:30:00Z", "2026-08-20T20:00:00Z"),
        _session("2026-08-21", "2026-08-21T13:30:00Z", "2026-08-21T20:00:00Z"),
    ]


def _instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def _iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _assert_code(code, func):
    with pytest.raises(V2ContractValidationError) as caught:
        func()
    assert caught.value.code == code


def _seal_clock(row):
    row = deepcopy(row)
    row.pop("semantic_hash", None)
    row.pop("record_hash", None)
    semantic = deepcopy(row)
    semantic.pop("recorded_at")
    row["semantic_hash"] = canonical_hash(semantic)
    record = deepcopy(row)
    row["record_hash"] = canonical_hash(record)
    return row


def _calendar_bundle(
    sessions=None,
    *,
    coverage_start=None,
    coverage_end=None,
    known_at=None,
    evidence_recorded_at=None,
    evidence_effective_from=None,
    evidence_effective_to=None,
):
    sessions = _regular_sessions() if sessions is None else list(sessions)
    dates = sorted(item["session_date"] for item in sessions)
    coverage_start = coverage_start or dates[0]
    coverage_end = coverage_end or dates[-1]
    payload = calendar_session_snapshot_payload(
        sessions,
        calendar_id=CALENDAR_ID,
        calendar_version=CALENDAR_VERSION,
        calendar_timezone=CALENDAR_TIMEZONE,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        coverage_complete=True,
    )
    earliest_open = min(_instant(item["open_at"]) for item in sessions)
    known_at = known_at or _iso(earliest_open - timedelta(days=2))
    evidence_recorded_at = evidence_recorded_at or _iso(
        _instant(known_at) + timedelta(minutes=1)
    )
    suffix = f"{coverage_start}-{coverage_end}"
    source = _source(
        source_contract_id=f"source-xnys-calendar-{suffix}-v1",
        provider="Authorized Calendar Publisher",
        source_name="xnys_complete_session_calendar",
        source_locator=f"https://calendar.example/{suffix}",
        decision_content_fields=sorted(payload),
        published_at_rule="The source exposes no separate publication timestamp.",
        published_at_field=None,
        known_at_rule="The complete calendar artifact is known at receipt.",
        decision_calendar=CALENDAR_ID,
        session_assignment_rule="Select only an explicit open session in the artifact.",
        revision_policy="immutable",
        security_mapping_policy="not_applicable",
        normalizer_id="xnys-session-calendar-normalizer",
        effective_from="2025-01-01T00:00:00Z",
        created_at="2025-01-01T00:00:00Z",
    )
    evidence = _evidence(
        source=source,
        evidence_id=f"evidence-xnys-calendar-{suffix}-r1",
        raw_identity={"event_id": f"calendar-{suffix}", "revision_id": "r1"},
        raw_artifact_locator=f"raw/calendars/xnys-{suffix}.json",
        raw_artifact_sha256=canonical_hash(payload),
        decision_content=payload,
        observed_at=known_at,
        published_at=None,
        known_at=known_at,
        known_at_basis="source receipt timestamp",
        effective_from=evidence_effective_from or known_at,
        effective_to=evidence_effective_to,
        recorded_at=evidence_recorded_at,
        security_scope="not_applicable",
        security_mapping_kind="not_applicable",
        security_mapping=None,
    )
    validate_evidence_against_source(evidence, source)
    return {
        "sessions": sessions,
        "payload": payload,
        "source": source,
        "evidence": evidence,
    }


def _clock(
    bundle,
    *,
    calendar_session_id=None,
    run_date=None,
    session_open_at=None,
    session_close_at=None,
    assignment_cutoff=None,
    frozen_at=None,
    recorded_at=None,
    anchor_kind="data_calendar",
    **overrides,
):
    sessions = bundle["sessions"]
    selected_id = calendar_session_id or sessions[0]["calendar_session_id"]
    selected = next(
        (item for item in sessions if item["calendar_session_id"] == selected_id),
        None,
    )
    if selected is None:
        if run_date is None or session_open_at is None or session_close_at is None:
            raise AssertionError("an absent synthetic session needs explicit bounds")
        selected = _session(
            run_date,
            session_open_at,
            session_close_at,
            calendar_session_id=selected_id,
        )
    normalized = CalendarSession.from_dict(
        selected, calendar_timezone=CALENDAR_TIMEZONE
    )
    selected_date = run_date or normalized.session_date
    selected_open = session_open_at or normalized.open_at
    selected_close = session_close_at or normalized.close_at
    open_dt = _instant(selected_open)
    cutoff = assignment_cutoff or _iso(open_dt - timedelta(hours=1))
    frozen = frozen_at or _iso(_instant(cutoff) + timedelta(minutes=10))
    recorded = recorded_at or _iso(_instant(cutoff) + timedelta(minutes=20))
    evidence = bundle["evidence"]
    snapshot_hash = canonical_hash(bundle["payload"])
    row = {
        "schema_version": 1,
        "record_type": "v2_session_clock",
        "session_clock_id": f"clock-{selected_id}-v1",
        "run_id": f"run-{selected_date}-v1",
        "run_date": selected_date,
        "calendar_id": CALENDAR_ID,
        "calendar_version": CALENDAR_VERSION,
        "calendar_timezone": CALENDAR_TIMEZONE,
        "calendar_snapshot_sha256": snapshot_hash,
        "calendar_snapshot_known_at": evidence["known_at"],
        "calendar_coverage_start": bundle["payload"]["coverage_start"],
        "calendar_coverage_end": bundle["payload"]["coverage_end"],
        "calendar_snapshot_complete": True,
        "calendar_evidence_id": evidence["evidence_id"],
        "calendar_evidence_record_hash": evidence["record_hash"],
        "calendar_session_id": selected_id,
        "session_open_at": selected_open,
        "session_close_at": selected_close,
        "anchor_kind": anchor_kind,
        "anchor_id": evidence["evidence_id"],
        "anchor_snapshot_sha256": evidence["decision_content_sha256"],
        "anchor_run_date": selected_date,
        "anchor_session_id": selected_id,
        "anchor_known_at": evidence["known_at"],
        "assignment_cutoff": cutoff,
        "frozen_at": frozen,
        "recorded_at": recorded,
        "process_wall_clock_fallback_used": False,
        "pit_tier": evidence["pit_tier"],
        "authority": "research_only",
        "trade_enabled": False,
        "semantic_hash": "0" * 64,
        "record_hash": "0" * 64,
    }
    row.update(overrides)
    return _seal_clock(row)


def _validate_clock(clock, bundle):
    return validate_session_clock_against_calendar(
        clock,
        bundle["sessions"],
        bundle["evidence"],
        bundle["source"],
    )


def _validate_bound(record, clock, bundle, **kwargs):
    return validate_record_against_session_clock(
        record,
        clock,
        bundle["sessions"],
        bundle["evidence"],
        bundle["source"],
        **kwargs,
    )


def _validate_event_clocks(event, run_clock, effective_clock, bundle):
    return validate_universe_event_against_session_clocks(
        event,
        run_clock=run_clock,
        run_calendar_sessions=bundle["sessions"],
        run_calendar_evidence=bundle["evidence"],
        run_calendar_source_contract=bundle["source"],
        effective_clock=effective_clock,
        effective_calendar_sessions=bundle["sessions"],
        effective_calendar_evidence=bundle["evidence"],
        effective_calendar_source_contract=bundle["source"],
    )


def _next_session_clock(bundle, **overrides):
    values = {
        "calendar_session_id": "XNYS-2026-08-21",
        "assignment_cutoff": "2026-08-20T12:30:00Z",
        "frozen_at": "2026-08-20T12:40:00Z",
        "recorded_at": "2026-08-20T12:50:00Z",
    }
    values.update(overrides)
    return _clock(bundle, **values)


def _decision_bound_to(clock):
    graph = _graph()
    return graph, _decision(
        graph,
        run_id=clock["run_id"],
        run_date=clock["run_date"],
        calendar_session_id=clock["calendar_session_id"],
        session_clock_id=clock["session_clock_id"],
        session_clock_hash=clock["semantic_hash"],
        session_clock_record_hash=clock["record_hash"],
    )


def _pool_bound_to(clock, **overrides):
    graph = _graph()
    pool = deepcopy(graph["pool"])
    pool.update(
        run_id=clock["run_id"],
        run_date=clock["run_date"],
        calendar_session_id=clock["calendar_session_id"],
        session_clock_id=clock["session_clock_id"],
        session_clock_hash=clock["semantic_hash"],
        session_clock_record_hash=clock["record_hash"],
    )
    pool.update(overrides)
    pool["input_snapshot_sha256"] = candidate_pool_input_snapshot_hash(
        hypothesis_candidate=graph["hypothesis"],
        evidence_records=graph["evidence"],
        universe_events=graph["events"],
        entries=pool["entries"],
        comparators=pool["comparators"],
        generator_rule_sha256=pool["generator_rule_sha256"],
        ranking_rule_sha256=pool["ranking_rule_sha256"],
        universe_id=pool["universe_id"],
        session_clock_id=pool["session_clock_id"],
        session_clock_hash=pool["session_clock_hash"],
        session_clock_record_hash=pool["session_clock_record_hash"],
        run_date=pool["run_date"],
        calendar_session_id=pool["calendar_session_id"],
        data_cutoff=pool["data_cutoff"],
    )
    return graph, _seal_pool(pool)


def _universe_event_bound_to(run_clock, effective_clock, *, effective_at=None):
    evidence = _evidence()
    event = _event(
        evidence=evidence,
        run_id=run_clock["run_id"],
        run_date=run_clock["run_date"],
        calendar_session_id=run_clock["calendar_session_id"],
        session_clock_id=run_clock["session_clock_id"],
        session_clock_hash=run_clock["semantic_hash"],
        session_clock_record_hash=run_clock["record_hash"],
        effective_at=effective_at or effective_clock["session_open_at"],
        effective_session_id=effective_clock["calendar_session_id"],
        effective_session_clock_id=effective_clock["session_clock_id"],
        effective_session_clock_hash=effective_clock["semantic_hash"],
        effective_session_clock_record_hash=effective_clock["record_hash"],
    )
    event["input_snapshot_sha256"] = universe_input_snapshot_hash(
        [evidence],
        rule_sha256=event["rule_sha256"],
        security_mapping_sha256=event["security_mapping"]["mapping_sha256"],
        session_clock_id=event["session_clock_id"],
        session_clock_hash=event["session_clock_hash"],
        session_clock_record_hash=event["session_clock_record_hash"],
        effective_session_clock_id=event["effective_session_clock_id"],
        effective_session_clock_hash=event["effective_session_clock_hash"],
        effective_session_clock_record_hash=event[
            "effective_session_clock_record_hash"
        ],
    )
    return _seal_event(event)


def _next_session_intent(decision, clock, **overrides):
    values = {
        "calendar_session_id": clock["calendar_session_id"],
        "session_clock_id": clock["session_clock_id"],
        "session_clock_hash": clock["semantic_hash"],
        "session_clock_record_hash": clock["record_hash"],
        "not_before": clock["session_open_at"],
        "expires_at": clock["session_close_at"],
    }
    values.update(overrides)
    return _intent(decision, **values)


def test_golden_calendar_payload_hash_is_bounded_complete_and_order_stable():
    sessions = _regular_sessions()
    payload = calendar_session_snapshot_payload(
        sessions,
        calendar_id=CALENDAR_ID,
        calendar_version=CALENDAR_VERSION,
        calendar_timezone=CALENDAR_TIMEZONE,
        coverage_start="2026-08-20",
        coverage_end="2026-08-21",
        coverage_complete=True,
    )
    assert payload["coverage_start"] == "2026-08-20"
    assert payload["coverage_end"] == "2026-08-21"
    assert payload["coverage_complete"] is True
    assert canonical_hash(payload) == GOLDEN_CALENDAR_HASH
    assert calendar_session_snapshot_hash(
        list(reversed(sessions)),
        calendar_id=CALENDAR_ID,
        calendar_version=CALENDAR_VERSION,
        calendar_timezone=CALENDAR_TIMEZONE,
        coverage_start="2026-08-20",
        coverage_end="2026-08-21",
        coverage_complete=True,
    ) == GOLDEN_CALENDAR_HASH


def test_clock_round_trip_binds_authorized_non_instrument_calendar_evidence():
    bundle = _calendar_bundle()
    row = _clock(bundle)
    original = deepcopy(row)

    clock = _validate_clock(row, bundle)

    assert isinstance(clock, SessionClock)
    assert normalize_session_clock(clock) == normalize_session_clock(row)
    assert row == original
    assert bundle["evidence"]["decision_content"] == bundle["payload"]
    assert row["anchor_id"] == bundle["evidence"]["evidence_id"]
    assert row["anchor_snapshot_sha256"] == bundle["evidence"][
        "decision_content_sha256"
    ]
    assert row["calendar_evidence_record_hash"] == bundle["evidence"]["record_hash"]
    assert row["anchor_snapshot_sha256"] != row["calendar_evidence_record_hash"]
    assert clock.process_wall_clock_fallback_used is False
    assert clock.trade_enabled is False
    assert clock.pit_tier == bundle["evidence"]["pit_tier"]
    assert CLOCK_BOUND_SCHEMA_VERSION == 2


@pytest.mark.parametrize("anchor_kind", ["frozen_run_date", "broker_session"])
def test_non_calendar_anchor_kinds_fail_closed(anchor_kind):
    row = _clock(_calendar_bundle(), anchor_kind=anchor_kind)
    _assert_code("invalid_enum", lambda: validate_session_clock(row))


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("process_wall_clock_fallback_used", True, "process_wall_clock_fallback_forbidden"),
        ("calendar_snapshot_complete", False, "complete_calendar_snapshot_required"),
        ("authority", "trading", "research_authority_required"),
        ("trade_enabled", True, "trade_enabled_forbidden"),
    ],
)
def test_clock_fails_closed_on_incomplete_or_escalated_state(field, value, code):
    row = _clock(_calendar_bundle())
    row[field] = value
    row = _seal_clock(row)
    _assert_code(code, lambda: validate_session_clock(row))


def test_clock_rejects_hash_tamper_and_calendar_anchor_cross_wires():
    bundle = _calendar_bundle()
    semantic_tamper = _clock(bundle)
    semantic_tamper["run_id"] = "unsealed-run-substitution"
    _assert_code("semantic_hash_mismatch", lambda: validate_session_clock(semantic_tamper))

    record_tamper = _clock(bundle)
    record_tamper["record_hash"] = "f" * 64
    _assert_code("hash_mismatch", lambda: validate_session_clock(record_tamper))

    wrong_anchor = _clock(bundle, anchor_snapshot_sha256="f" * 64)
    _assert_code(
        "calendar_anchor_evidence_mismatch", lambda: validate_session_clock(wrong_anchor)
    )


def test_calendar_reconciliation_rejects_content_and_late_evidence():
    bundle = _calendar_bundle()
    clock = _clock(bundle)
    changed_sessions = [
        *_regular_sessions(),
        _session("2026-08-22", "2026-08-22T13:30:00Z", "2026-08-22T20:00:00Z"),
    ]
    _assert_code(
        "calendar_session_outside_coverage",
        lambda: validate_session_clock_against_calendar(
            clock, changed_sessions, bundle["evidence"], bundle["source"]
        ),
    )
    changed_in_coverage = deepcopy(_regular_sessions())
    changed_in_coverage[1]["close_at"] = "2026-08-21T19:59:00Z"
    _assert_code(
        "calendar_snapshot_hash_mismatch",
        lambda: validate_session_clock_against_calendar(
            clock,
            changed_in_coverage,
            bundle["evidence"],
            bundle["source"],
        ),
    )

    late_bundle = _calendar_bundle(
        known_at="2026-08-20T11:00:00Z",
        evidence_recorded_at="2026-08-20T12:31:00Z",
    )
    late_clock = _clock(
        late_bundle,
        assignment_cutoff="2026-08-20T12:30:00Z",
        frozen_at="2026-08-20T12:40:00Z",
        recorded_at="2026-08-20T12:50:00Z",
    )
    _assert_code(
        "calendar_evidence_recorded_after_cutoff",
        lambda: _validate_clock(late_clock, late_bundle),
    )


@pytest.mark.parametrize(
    ("effective_from", "effective_to"),
    [
        ("2026-09-01T00:00:00Z", None),
        ("2026-08-18T00:00:00Z", "2026-08-20T13:30:00Z"),
    ],
)
def test_selected_session_must_fall_inside_calendar_evidence_interval(
    effective_from, effective_to
):
    bundle = _calendar_bundle(
        evidence_effective_from=effective_from,
        evidence_effective_to=effective_to,
    )
    _assert_code(
        "calendar_evidence_interval_miss",
        lambda: _validate_clock(_clock(bundle), bundle),
    )


def test_assignment_cannot_use_calendar_evidence_after_its_interval():
    bundle = _calendar_bundle(
        evidence_effective_to="2026-08-20T14:00:00Z"
    )
    clock = _clock(
        bundle,
        assignment_cutoff="2026-08-20T15:00:00Z",
        frozen_at="2026-08-20T15:10:00Z",
        recorded_at="2026-08-20T15:20:00Z",
    )
    _assert_code(
        "calendar_evidence_interval_miss",
        lambda: _validate_clock(clock, bundle),
    )


def test_calendar_pit_tier_is_frozen_and_caps_clock_bound_records():
    bundle = _calendar_bundle()
    clock = _clock(bundle)

    overstated_clock = deepcopy(clock)
    overstated_clock["pit_tier"] = "canonical_pit"
    overstated_clock = _seal_clock(overstated_clock)
    _assert_code(
        "calendar_pit_tier_mismatch",
        lambda: _validate_clock(overstated_clock, bundle),
    )

    _, pool = _pool_bound_to(clock)
    canonical_pool = deepcopy(pool)
    canonical_pool["pit_tier"] = "canonical_pit"
    canonical_pool["result_ceiling"] = "gate_eligible"
    canonical_pool = _seal_pool(canonical_pool)
    _assert_code(
        "pit_tier_exceeds_session_clock",
        lambda: _validate_bound(canonical_pool, clock, bundle),
    )


@pytest.mark.parametrize(
    ("missing_date", "open_at", "close_at", "coverage_start", "coverage_end", "sessions"),
    [
        (
            "2026-08-22",
            "2026-08-22T13:30:00Z",
            "2026-08-22T20:00:00Z",
            "2026-08-21",
            "2026-08-24",
            [
                _session("2026-08-21", "2026-08-21T13:30:00Z", "2026-08-21T20:00:00Z"),
                _session("2026-08-24", "2026-08-24T13:30:00Z", "2026-08-24T20:00:00Z"),
            ],
        ),
        (
            "2026-12-25",
            "2026-12-25T14:30:00Z",
            "2026-12-25T21:00:00Z",
            "2026-12-24",
            "2026-12-28",
            [
                _session("2026-12-24", "2026-12-24T14:30:00Z", "2026-12-24T18:00:00Z", session_kind="early_close"),
                _session("2026-12-28", "2026-12-28T14:30:00Z", "2026-12-28T21:00:00Z"),
            ],
        ),
    ],
)
def test_complete_calendar_never_infers_weekend_or_special_closure(
    missing_date, open_at, close_at, coverage_start, coverage_end, sessions
):
    bundle = _calendar_bundle(
        sessions, coverage_start=coverage_start, coverage_end=coverage_end
    )
    clock = _clock(
        bundle,
        calendar_session_id=f"XNYS-{missing_date}",
        run_date=missing_date,
        session_open_at=open_at,
        session_close_at=close_at,
    )
    _assert_code("unresolved_calendar_session", lambda: _validate_clock(clock, bundle))


def test_early_close_and_dst_use_exact_authoritative_bounds():
    early_sessions = [
        _session(
            "2026-11-27",
            "2026-11-27T14:30:00Z",
            "2026-11-27T18:00:00Z",
            session_kind="early_close",
        )
    ]
    early_bundle = _calendar_bundle(early_sessions)
    assert _validate_clock(_clock(early_bundle), early_bundle).session_close_at == (
        "2026-11-27T18:00:00Z"
    )
    wrong_close = _clock(early_bundle, session_close_at="2026-11-27T21:00:00Z")
    _assert_code("calendar_session_bounds_mismatch", lambda: _validate_clock(wrong_close, early_bundle))

    local_sessions = [
        _session("2026-03-06", "2026-03-06T09:30:00-05:00", "2026-03-06T16:00:00-05:00"),
        _session("2026-03-09", "2026-03-09T09:30:00-04:00", "2026-03-09T16:00:00-04:00"),
    ]
    dst_bundle = _calendar_bundle(local_sessions)
    before = _validate_clock(
        _clock(dst_bundle, calendar_session_id="XNYS-2026-03-06"), dst_bundle
    )
    after = _validate_clock(
        _clock(dst_bundle, calendar_session_id="XNYS-2026-03-09"), dst_bundle
    )
    assert before.session_open_at == "2026-03-06T14:30:00Z"
    assert after.session_open_at == "2026-03-09T13:30:00Z"


def test_session_clock_append_only_append_duplicate_and_conflict():
    bundle = _calendar_bundle()
    first = _clock(bundle, recorded_at="2026-08-20T12:50:00Z")
    retry = _clock(bundle, recorded_at="2026-08-20T13:00:00Z")
    conflict = _clock(
        bundle,
        assignment_cutoff="2026-08-20T12:31:00Z",
        frozen_at="2026-08-20T12:41:00Z",
        recorded_at="2026-08-20T12:51:00Z",
    )

    assert first["semantic_hash"] == retry["semantic_hash"]
    assert first["record_hash"] != retry["record_hash"]
    assert validate_append_only_append([], first) == "append"
    assert validate_append_only_append([first], retry) == "duplicate"
    _assert_code(
        "immutable_key_conflict",
        lambda: validate_append_only_append([first], conflict),
    )


def test_candidate_pool_binds_exact_clock_record_not_semantic_retry():
    bundle = _calendar_bundle()
    clock = _clock(bundle)
    _, pool = _pool_bound_to(clock)

    assert isinstance(_validate_bound(pool, clock, bundle), CandidatePool)
    retry = _clock(bundle, recorded_at="2026-08-20T13:00:00Z")
    assert retry["semantic_hash"] == clock["semantic_hash"]
    _assert_code(
        "session_clock_binding_mismatch",
        lambda: _validate_bound(pool, retry, bundle),
    )


def test_resealed_decision_clock_substitution_fails_exact_binding():
    bundle = _calendar_bundle()
    expected = _clock(bundle)
    graph, decision = _decision_bound_to(expected)
    assert isinstance(_validate_bound(decision, expected, bundle), DecisionRecord)

    substitute = _clock(
        bundle,
        assignment_cutoff="2026-08-20T12:31:00Z",
        frozen_at="2026-08-20T12:41:00Z",
        recorded_at="2026-08-20T12:51:00Z",
    )
    substituted = _decision(
        graph,
        run_id=substitute["run_id"],
        run_date=substitute["run_date"],
        calendar_session_id=substitute["calendar_session_id"],
        session_clock_id=substitute["session_clock_id"],
        session_clock_hash=substitute["semantic_hash"],
        session_clock_record_hash=substitute["record_hash"],
    )
    validate_decision_record(substituted)
    _assert_code(
        "session_clock_binding_mismatch",
        lambda: _validate_bound(substituted, expected, bundle),
    )


def test_decision_candidate_pool_cross_validator_rejects_clock_cross_wire():
    bundle = _calendar_bundle()
    expected = _clock(bundle)
    substitute = _clock(
        bundle,
        assignment_cutoff="2026-08-20T12:31:00Z",
        frozen_at="2026-08-20T12:41:00Z",
        recorded_at="2026-08-20T12:51:00Z",
    )
    graph, pool = _pool_bound_to(expected)
    graph = deepcopy(graph)
    graph["pool"] = pool
    decision = _decision(
        graph,
        session_clock_id=substitute["session_clock_id"],
        session_clock_hash=substitute["semantic_hash"],
        session_clock_record_hash=substitute["record_hash"],
    )

    _assert_code(
        "decision_clock_identity_mismatch",
        lambda: validate_decision_record_against_candidate_pool(
            decision, pool, graph["hypothesis"]
        ),
    )


def test_universe_event_binds_run_and_next_session_effective_clocks():
    bundle = _calendar_bundle()
    run_clock = _clock(bundle)
    effective_clock = _next_session_clock(bundle)
    event = _universe_event_bound_to(run_clock, effective_clock)

    assert effective_clock["recorded_at"] < event["decided_at"]
    assert bundle["evidence"]["recorded_at"] < event["decided_at"]
    assert isinstance(_validate_bound(event, run_clock, bundle, role="run"), UniverseEvent)
    assert isinstance(
        _validate_bound(event, effective_clock, bundle, role="effective"), UniverseEvent
    )
    assert isinstance(
        _validate_event_clocks(event, run_clock, effective_clock, bundle),
        UniverseEvent,
    )
    _assert_code(
        "session_clock_role_required",
        lambda: _validate_bound(event, run_clock, bundle),
    )

    substitute = _next_session_clock(bundle, recorded_at="2026-08-20T13:00:00Z")
    substituted_event = _universe_event_bound_to(run_clock, substitute)
    _assert_code(
        "session_clock_binding_mismatch",
        lambda: _validate_bound(
            substituted_event, effective_clock, bundle, role="effective"
        ),
    )
    _assert_code(
        "session_clock_binding_mismatch",
        lambda: _validate_event_clocks(
            event, run_clock, substitute, bundle
        ),
    )


def test_effective_session_cannot_precede_owning_run_clock():
    bundle = _calendar_bundle()
    run_clock = _next_session_clock(bundle)
    earlier_effective_clock = _clock(bundle)
    event = _universe_event_bound_to(
        run_clock,
        earlier_effective_clock,
        effective_at="2026-08-20T14:06:00Z",
    )

    _assert_code(
        "effective_session_precedes_run_date",
        lambda: _validate_bound(
            event, earlier_effective_clock, bundle, role="effective"
        ),
    )
    _assert_code(
        "run_clock_use_date_mismatch",
        lambda: _validate_event_clocks(
            event, run_clock, earlier_effective_clock, bundle
        ),
    )


def test_run_clock_cannot_be_reused_for_a_later_local_date():
    bundle = _calendar_bundle()
    clock = _clock(bundle)
    _, pool = _pool_bound_to(
        clock,
        data_cutoff="2027-01-05T14:00:00Z",
        frozen_at="2027-01-05T14:10:00Z",
        recorded_at="2027-01-05T14:11:00Z",
    )
    _assert_code(
        "run_clock_use_date_mismatch",
        lambda: _validate_bound(pool, clock, bundle),
    )


@pytest.mark.parametrize(
    "effective_at",
    ["2026-08-21T13:29:59Z", "2026-08-21T20:00:01Z"],
)
def test_effective_event_cannot_fall_before_open_or_after_close(effective_at):
    bundle = _calendar_bundle()
    run_clock = _clock(bundle)
    effective_clock = _next_session_clock(bundle)
    event = _universe_event_bound_to(
        run_clock, effective_clock, effective_at=effective_at
    )
    _assert_code(
        "effective_at_outside_session",
        lambda: _validate_bound(event, effective_clock, bundle, role="effective"),
    )


def test_effective_clock_recorded_after_event_decision_fails_closed():
    bundle = _calendar_bundle()
    run_clock = _clock(bundle)
    late_clock = _next_session_clock(
        bundle,
        assignment_cutoff="2026-08-20T13:40:00Z",
        frozen_at="2026-08-20T13:50:00Z",
        recorded_at="2026-08-20T14:05:00Z",
    )
    event = _universe_event_bound_to(run_clock, late_clock)
    _assert_code(
        "session_clock_recorded_after_use",
        lambda: _validate_bound(event, late_clock, bundle, role="effective"),
    )


def test_next_session_intent_binding_window_substitution_and_gtc_fail_closed():
    bundle = _calendar_bundle()
    _, decision = _decision_bound_to(_clock(bundle))
    execution_clock = _next_session_clock(bundle)
    intent = _next_session_intent(decision, execution_clock)
    validate_order_intent_against_decision(intent, decision)
    assert isinstance(_validate_bound(intent, execution_clock, bundle), OrderIntent)

    substitute = _next_session_clock(bundle, recorded_at="2026-08-20T13:00:00Z")
    substituted_intent = _next_session_intent(decision, substitute)
    _assert_code(
        "session_clock_binding_mismatch",
        lambda: _validate_bound(substituted_intent, execution_clock, bundle),
    )

    before_open = _next_session_intent(
        decision, execution_clock, not_before="2026-08-21T13:29:59Z"
    )
    _assert_code(
        "order_window_outside_session",
        lambda: _validate_bound(before_open, execution_clock, bundle),
    )

    gtc = _next_session_intent(decision, execution_clock, time_in_force="gtc")
    validate_order_intent(gtc)
    _assert_code(
        "multisession_intent_clock_unsupported",
        lambda: _validate_bound(gtc, execution_clock, bundle),
    )


def test_clock_bound_schema_v1_records_are_rejected():
    graph = _graph()
    decision = _decision(graph)
    intent = _intent(decision)
    records = [
        (validate_universe_event, graph["events"][0]),
        (validate_candidate_pool, graph["pool"]),
        (validate_decision_record, decision),
        (validate_order_intent, intent),
    ]
    for validator, row in records:
        legacy = deepcopy(row)
        legacy["schema_version"] = 1
        _assert_code("unsupported_schema_version", lambda: validator(legacy))
