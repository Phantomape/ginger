from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json

import pytest

import quant.v2_contracts as contracts_module
import quant.v2_universe_ledger as ledger_module
from quant.test_v2_contracts import _evidence, _mapping, _seal_event, _source
from quant.test_v2_research_contracts import _event_for, _graph
from quant.test_v2_session_clock_contracts import _calendar_bundle, _clock
from quant.v2_contracts import (
    canonical_hash,
    universe_input_snapshot_hash,
    validate_universe_event_against_evidence,
    validate_universe_event_against_session_clocks,
)
from quant.v2_universe_ledger import (
    V2UniverseLedgerError,
    append_v2_universe_batch,
    build_universe_membership_manifest,
    load_v2_universe_ledger,
    read_v2_daily_universe,
    read_v2_replay_universe,
    read_v2_universe_membership,
    validate_universe_event_population,
    validate_universe_membership_manifest,
)


UNIVERSE_ID = "v2-research-universe"
DEFINITION_ID = "v2-dynamic-research-universe"
DEFINITION_VERSION = "1"
DEFINITION_HASH = canonical_hash(
    {
        "universe_definition_id": DEFINITION_ID,
        "universe_definition_version": DEFINITION_VERSION,
        "eligibility_source": "synthetic-contract-test-only",
    }
)


def _assert_code(code, func):
    with pytest.raises(V2UniverseLedgerError) as caught:
        func()
    assert caught.value.code == code


def _bound_graph(*, quarantine_second=True):
    graph = _graph(two_candidates=True)
    bundle = _calendar_bundle()
    clock = _clock(bundle)
    raw_events = deepcopy(graph["events"])
    if quarantine_second:
        bbb = [
            event
            for event in raw_events
            if event["security_mapping"]["security_id"] == "sec-bbb"
        ]
        latest = max(bbb, key=lambda event: event["effective_at"])
        latest["to_state"] = "quarantine"
        latest["reason_code"] = "synthetic_quarantine"
        latest["reason"] = "Synthetic non-eligible latest state for completeness."

    evidence_by_id = {item["evidence_id"]: item for item in graph["evidence"]}
    by_security = {}
    for event in raw_events:
        security_id = event["security_mapping"]["security_id"]
        by_security.setdefault(security_id, []).append(event)

    events = []
    for security_id in sorted(by_security):
        previous = None
        for raw in sorted(by_security[security_id], key=lambda item: item["effective_at"]):
            row = deepcopy(raw)
            row["run_id"] = clock["run_id"]
            row["session_clock_id"] = clock["session_clock_id"]
            row["session_clock_hash"] = clock["semantic_hash"]
            row["session_clock_record_hash"] = clock["record_hash"]
            row["run_date"] = clock["run_date"]
            row["calendar_session_id"] = clock["calendar_session_id"]
            row["effective_session_id"] = clock["calendar_session_id"]
            row["effective_session_clock_id"] = clock["session_clock_id"]
            row["effective_session_clock_hash"] = clock["semantic_hash"]
            row["effective_session_clock_record_hash"] = clock["record_hash"]
            if previous is not None:
                row["previous_event_id"] = previous["event_id"]
                row["previous_event_hash"] = previous["event_hash"]
                row["from_state"] = previous["to_state"]
            evidence = [evidence_by_id[item] for item in row["evidence_record_ids"]]
            row["input_snapshot_sha256"] = universe_input_snapshot_hash(
                evidence,
                rule_sha256=row["rule_sha256"],
                security_mapping_sha256=row["security_mapping"]["mapping_sha256"],
                session_clock_id=row["session_clock_id"],
                session_clock_hash=row["session_clock_hash"],
                session_clock_record_hash=row["session_clock_record_hash"],
                effective_session_clock_id=row["effective_session_clock_id"],
                effective_session_clock_hash=row["effective_session_clock_hash"],
                effective_session_clock_record_hash=row[
                    "effective_session_clock_record_hash"
                ],
            )
            row = _seal_event(row)
            validate_universe_event_against_evidence(
                row, graph["evidence"], [graph["source"]]
            )
            validate_universe_event_against_session_clocks(
                row,
                run_clock=clock,
                run_calendar_sessions=bundle["sessions"],
                run_calendar_evidence=bundle["evidence"],
                run_calendar_source_contract=bundle["source"],
                effective_clock=clock,
                effective_calendar_sessions=bundle["sessions"],
                effective_calendar_evidence=bundle["evidence"],
                effective_calendar_source_contract=bundle["source"],
            )
            events.append(row)
            previous = row
    return graph, bundle, clock, events


def _manifest(
    events,
    clock,
    *,
    previous=None,
    suffix="1",
    graph=None,
    bundle=None,
    effective_bundle=None,
    **overrides,
):
    if graph is None or bundle is None:
        default_graph, default_bundle, _, _ = _bound_graph()
        graph = default_graph if graph is None else graph
        bundle = default_bundle if bundle is None else bundle
    effective_bundle = bundle if effective_bundle is None else effective_bundle
    values = {
        "manifest_id": f"universe-manifest-20260820-{suffix}",
        "universe_id": UNIVERSE_ID,
        "event_batch_id": f"universe-batch-20260820-{suffix}",
        "universe_definition_id": DEFINITION_ID,
        "universe_definition_version": DEFINITION_VERSION,
        "universe_definition_sha256": DEFINITION_HASH,
        "source_contracts": [
            graph["source"],
            bundle["source"],
            effective_bundle["source"],
        ],
        "evidence_records": [
            *graph["evidence"],
            bundle["evidence"],
            effective_bundle["evidence"],
        ],
        "run_clock": clock,
        "effective_clock": clock,
        "ledger_population_start": "2026-08-20T13:30:00Z",
        "membership_as_of": "2026-08-20T14:20:00Z",
        "data_cutoff": "2026-08-20T14:20:00Z",
        "frozen_at": "2026-08-20T14:21:00Z",
        "recorded_at": "2026-08-20T14:22:00Z",
        "previous_manifest": previous,
    }
    values.update(overrides)
    return build_universe_membership_manifest(events, **values)


def _append(
    path,
    events,
    manifest,
    *,
    graph,
    bundle,
    clock,
    effective_clock=None,
    effective_bundle=None,
    evidence_records=None,
    source_contracts=None,
    **overrides,
):
    effective_clock = clock if effective_clock is None else effective_clock
    effective_bundle = bundle if effective_bundle is None else effective_bundle
    evidence_records = graph["evidence"] if evidence_records is None else evidence_records
    source_contracts = [graph["source"]] if source_contracts is None else source_contracts
    return append_v2_universe_batch(
        path,
        events,
        manifest,
        run_clock=clock,
        effective_clock=effective_clock,
        evidence_records=evidence_records,
        source_contracts=source_contracts,
        run_calendar_sessions=bundle["sessions"],
        run_calendar_evidence=bundle["evidence"],
        run_calendar_source_contract=bundle["source"],
        effective_calendar_sessions=effective_bundle["sessions"],
        effective_calendar_evidence=effective_bundle["evidence"],
        effective_calendar_source_contract=effective_bundle["source"],
        **overrides,
    )


def _transition_event(
    graph,
    clock,
    previous,
    *,
    suffix="2",
    decided_at="2026-08-20T14:23:00Z",
    recorded_at="2026-08-20T14:24:00Z",
    effective_at="2026-08-20T14:25:00Z",
    effective_clock=None,
    mapping=None,
):
    effective_clock = clock if effective_clock is None else effective_clock
    mapping = previous["security_mapping"] if mapping is None else mapping
    return _event_for(
        evidence=graph["evidence"][0],
        mapping=mapping,
        event_id=f"sec-aaa-quarantine-after-manifest-{suffix}",
        event_batch_id=f"universe-batch-20260820-{suffix}",
        event_type="state_transition",
        from_state=previous["to_state"],
        to_state="quarantine",
        previous_event_id=previous["event_id"],
        previous_event_hash=previous["event_hash"],
        reason_code="synthetic_quarantine",
        reason="Synthetic later-batch transition.",
        run_id=clock["run_id"],
        session_clock_id=clock["session_clock_id"],
        session_clock_hash=clock["semantic_hash"],
        session_clock_record_hash=clock["record_hash"],
        run_date=clock["run_date"],
        calendar_session_id=clock["calendar_session_id"],
        effective_session_id=effective_clock["calendar_session_id"],
        effective_session_clock_id=effective_clock["session_clock_id"],
        effective_session_clock_hash=effective_clock["semantic_hash"],
        effective_session_clock_record_hash=effective_clock["record_hash"],
        decided_at=decided_at,
        recorded_at=recorded_at,
        effective_at=effective_at,
    )


def _reseal_manifest(row):
    row = deepcopy(row)
    row.pop("semantic_hash", None)
    row.pop("manifest_hash", None)
    row["semantic_hash"] = canonical_hash(ledger_module._manifest_semantic_payload(row))
    row["manifest_hash"] = canonical_hash(ledger_module._manifest_record_payload(row))
    return row


def test_manifest_derives_all_state_ledger_membership_and_exact_clock_bindings():
    _, _, clock, events = _bound_graph()
    manifest = _manifest(events, clock)

    validated = validate_universe_membership_manifest(
        manifest,
        events=events,
        run_clock=clock,
        effective_clock=clock,
    )
    assert validated == manifest
    assert {row["state"] for row in manifest["memberships"]} == {
        "candidate_eligible",
        "quarantine",
    }
    assert len(manifest["memberships"]) == 2
    assert manifest["universe_event_ids"] == sorted(
        event["event_id"] for event in events
    )
    assert manifest["session_clock_record_hash"] == clock["record_hash"]
    assert (
        manifest["session_clock_calendar_evidence_id"]
        == clock["calendar_evidence_id"]
    )
    assert (
        manifest["session_clock_calendar_evidence_record_hash"]
        == clock["calendar_evidence_record_hash"]
    )
    assert manifest["pit_tier"] == "research_pit"
    assert manifest["ledger_population_complete"] is True
    assert manifest["external_universe_coverage_status"] == "unverified"
    assert manifest["paper_live_eligible"] is False
    assert manifest["trade_enabled"] is False


def test_empty_ledger_population_is_valid_but_missing_and_prestart_are_unknown(tmp_path):
    graph, bundle, clock, _ = _bound_graph()
    path = tmp_path / "universe.jsonl"
    manifest = _manifest([], clock, suffix="empty")

    result = _append(
        path, [], manifest, graph=graph, bundle=bundle, clock=clock
    )
    assert result["status"] == "appended"
    snapshot = read_v2_universe_membership(
        path,
        manifest_id=manifest["manifest_id"],
        as_of="2026-08-20T14:00:00Z",
    )
    assert snapshot["memberships"] == []
    assert snapshot["ledger_population_complete"] is True
    assert snapshot["external_universe_coverage_status"] == "unverified"

    _assert_code(
        "universe_ledger_missing",
        lambda: load_v2_universe_ledger(tmp_path / "missing.jsonl"),
    )
    _assert_code(
        "as_of_before_ledger_population",
        lambda: read_v2_universe_membership(
            path,
            manifest_id=manifest["manifest_id"],
            as_of="2026-08-20T13:29:59Z",
        ),
    )


def test_atomic_append_is_idempotent_and_daily_replay_are_true_aliases(
    tmp_path, monkeypatch
):
    graph, bundle, clock, events = _bound_graph()
    path = tmp_path / "universe.jsonl"
    manifest = _manifest(events, clock)
    writes = []
    real_write = ledger_module.atomic_write_text

    def counted_write(text, filepath):
        writes.append(text)
        real_write(text, filepath)

    monkeypatch.setattr(ledger_module, "atomic_write_text", counted_write)
    first = _append(
        path, events, manifest, graph=graph, bundle=bundle, clock=clock
    )
    retry = _append(
        path, events, manifest, graph=graph, bundle=bundle, clock=clock
    )

    assert first["status"] == "appended"
    assert retry["status"] == "duplicate"
    assert len(writes) == 1
    assert read_v2_daily_universe is read_v2_universe_membership
    assert read_v2_replay_universe is read_v2_universe_membership
    daily = read_v2_daily_universe(
        path,
        manifest_id=manifest["manifest_id"],
        as_of=manifest["membership_as_of"],
    )
    replay = read_v2_replay_universe(
        path,
        manifest_id=manifest["manifest_id"],
        as_of=manifest["membership_as_of"],
    )
    assert daily == replay
    assert daily["snapshot_hash"] == replay["snapshot_hash"]
    assert daily["memberships"] == manifest["memberships"]
    assert (
        daily["membership_snapshot_sha256"]
        == manifest["membership_snapshot_sha256"]
    )


def test_event_prefix_validation_scales_linearly_for_load_and_write(
    tmp_path, monkeypatch
):
    graph, bundle, clock, events = _bound_graph()
    populations = (
        [
            event
            for event in events
            if event["security_mapping"]["security_id"] == "sec-aaa"
        ],
        events,
    )
    load_counts = []
    write_counts = []

    def count_event_validations(call):
        validation_calls = 0
        real_validate = ledger_module.validate_universe_event

        def counted_validate(value):
            nonlocal validation_calls
            validation_calls += 1
            return real_validate(value)

        with monkeypatch.context() as patch:
            patch.setattr(ledger_module, "validate_universe_event", counted_validate)
            patch.setattr(contracts_module, "validate_universe_event", counted_validate)
            result = call()
        return validation_calls, result

    for index, population in enumerate(populations, start=1):
        manifest = _manifest(
            population,
            clock,
            suffix=f"scale-{index}",
            graph=graph,
            bundle=bundle,
            event_batch_id=population[0]["event_batch_id"],
        )
        path = tmp_path / f"scale-{index}.jsonl"
        path.write_text(
            "".join(ledger_module.canonical_json(event) + "\n" for event in population)
            + ledger_module.canonical_json(manifest)
            + "\n",
            encoding="utf-8",
        )
        load_calls, loaded = count_event_validations(
            lambda: load_v2_universe_ledger(path)
        )
        write_calls, written = count_event_validations(
            lambda: _append(
                tmp_path / f"writer-scale-{index}.jsonl",
                population,
                manifest,
                graph=graph,
                bundle=bundle,
                clock=clock,
            )
        )

        assert len(loaded["events"]) == len(population)
        assert len(loaded["manifests"]) == 1
        assert written["status"] == "appended"
        load_counts.append(load_calls)
        write_counts.append(write_calls)

    assert load_counts[1] <= 2 * load_counts[0]
    assert write_counts[1] <= 2 * write_counts[0]


def test_writer_rejects_event_id_with_changed_semantics(tmp_path):
    graph, bundle, clock, events = _bound_graph()
    path = tmp_path / "universe.jsonl"
    first = _manifest(events, clock)
    _append(path, events, first, graph=graph, bundle=bundle, clock=clock)
    original = path.read_bytes()

    changed = deepcopy(events[2])
    changed["reason"] = "Same immutable event ID with changed semantics."
    changed = _seal_event(changed)
    changed_population = [*events[:2], changed, *events[3:]]
    successor = _manifest(
        changed_population,
        clock,
        previous=first,
        suffix="event-conflict",
        data_cutoff="2026-08-20T14:21:00Z",
        frozen_at="2026-08-20T14:22:00Z",
        recorded_at="2026-08-20T14:23:00Z",
    )

    _assert_code(
        "universe_event_id_conflict",
        lambda: _append(
            path,
            [changed],
            successor,
            graph=graph,
            bundle=bundle,
            clock=clock,
        ),
    )
    assert path.read_bytes() == original


def test_equivalent_utc_offsets_produce_identical_membership_snapshot(tmp_path):
    graph, bundle, clock, events = _bound_graph()
    path = tmp_path / "universe.jsonl"
    manifest = _manifest(events, clock)
    _append(path, events, manifest, graph=graph, bundle=bundle, clock=clock)

    utc = read_v2_universe_membership(
        path,
        manifest_id=manifest["manifest_id"],
        as_of="2026-08-20T14:20:00Z",
    )
    offset = read_v2_universe_membership(
        path,
        manifest_id=manifest["manifest_id"],
        as_of="2026-08-20T07:20:00-07:00",
    )

    assert utc == offset
    assert offset["as_of"] == "2026-08-20T14:20:00Z"


def test_writer_rejects_missing_evidence_and_foreign_event_clock(tmp_path):
    graph, bundle, clock, events = _bound_graph()
    manifest = _manifest(events, clock)
    missing = deepcopy(graph)
    missing["evidence"] = []
    _assert_code(
        "unresolved_evidence_id",
        lambda: _append(
            tmp_path / "missing-evidence.jsonl",
            events,
            manifest,
            graph=missing,
            bundle=bundle,
            clock=clock,
        ),
    )

    forged = deepcopy(events)
    latest_index = max(
        (
            index
            for index, event in enumerate(forged)
            if event["security_mapping"]["security_id"] == "sec-aaa"
        ),
        key=lambda index: forged[index]["effective_at"],
    )
    forged[latest_index]["run_id"] = "foreign-run-id"
    forged[latest_index] = _seal_event(forged[latest_index])
    _assert_code(
        "manifest_event_clock_binding_mismatch",
        lambda: _manifest(forged, clock),
    )


def test_writer_rejects_cross_registry_stable_id_aliases(tmp_path):
    graph, bundle, clock, events = _bound_graph()
    manifest = _manifest(events, clock)
    source_alias = _source(provider="Conflicting Provider")
    _assert_code(
        "source_contract_id_conflict",
        lambda: _append(
            tmp_path / "source-alias.jsonl",
            events,
            manifest,
            graph=graph,
            bundle=bundle,
            clock=clock,
            source_contracts=[graph["source"], source_alias],
        ),
    )

    evidence_alias = _evidence(
        source=graph["source"],
        evidence_id=graph["evidence"][0]["evidence_id"],
        raw_artifact_locator="raw/official/conflicting-event-1-r1.json",
        raw_artifact_sha256="9" * 64,
    )
    _assert_code(
        "evidence_id_conflict",
        lambda: _append(
            tmp_path / "evidence-alias.jsonl",
            events,
            manifest,
            graph=graph,
            bundle=bundle,
            clock=clock,
            evidence_records=[*graph["evidence"], evidence_alias],
        ),
    )

    clock_alias = _clock(
        bundle,
        calendar_session_id="XNYS-2026-08-21",
        assignment_cutoff="2026-08-20T14:17:00Z",
        frozen_at="2026-08-20T14:18:00Z",
        recorded_at="2026-08-20T14:19:00Z",
        session_clock_id=clock["session_clock_id"],
    )
    _assert_code(
        "session_clock_id_conflict",
        lambda: _manifest(
            [],
            clock,
            suffix="clock-alias",
            effective_clock=clock_alias,
        ),
    )


def test_writer_rejects_source_and_evidence_id_forks_across_batches(tmp_path):
    graph, bundle, clock, events = _bound_graph()
    path = tmp_path / "universe.jsonl"
    first = _manifest(events, clock)
    _append(path, events, first, graph=graph, bundle=bundle, clock=clock)
    second = _manifest(
        events,
        clock,
        previous=first,
        suffix="2",
        data_cutoff="2026-08-20T14:21:00Z",
        frozen_at="2026-08-20T14:22:00Z",
        recorded_at="2026-08-20T14:23:00Z",
    )

    source_alias = _source(provider="Cross-batch Conflicting Provider")
    _assert_code(
        "source_contract_id_conflict",
        lambda: _append(
            path,
            [],
            second,
            graph=graph,
            bundle=bundle,
            clock=clock,
            evidence_records=[],
            source_contracts=[source_alias],
        ),
    )
    evidence_alias = _evidence(
        source=graph["source"],
        evidence_id=graph["evidence"][0]["evidence_id"],
        raw_artifact_locator="raw/official/cross-batch-conflict.json",
        raw_artifact_sha256="8" * 64,
    )
    _assert_code(
        "evidence_id_conflict",
        lambda: _append(
            path,
            [],
            second,
            graph=graph,
            bundle=bundle,
            clock=clock,
            evidence_records=[evidence_alias],
            source_contracts=[graph["source"]],
        ),
    )
    assert len(load_v2_universe_ledger(path)["manifests"]) == 1


def test_population_rejects_rule_and_mapping_identity_forks():
    graph, _, clock, events = _bound_graph(quarantine_second=False)
    previous = max(
        (
            event
            for event in events
            if event["security_mapping"]["security_id"] == "sec-aaa"
        ),
        key=lambda event: event["effective_at"],
    )
    rule_fork = _transition_event(graph, clock, previous)
    rule_fork["rule_sha256"] = "a" * 64
    rule_fork["input_snapshot_sha256"] = universe_input_snapshot_hash(
        [graph["evidence"][0]],
        rule_sha256=rule_fork["rule_sha256"],
        security_mapping_sha256=rule_fork["security_mapping"]["mapping_sha256"],
        session_clock_id=rule_fork["session_clock_id"],
        session_clock_hash=rule_fork["session_clock_hash"],
        session_clock_record_hash=rule_fork["session_clock_record_hash"],
        effective_session_clock_id=rule_fork["effective_session_clock_id"],
        effective_session_clock_hash=rule_fork["effective_session_clock_hash"],
        effective_session_clock_record_hash=rule_fork[
            "effective_session_clock_record_hash"
        ],
    )
    rule_fork = _seal_event(rule_fork)
    _assert_code(
        "universe_rule_identity_conflict",
        lambda: validate_universe_event_population(
            [*events, rule_fork], universe_id=UNIVERSE_ID
        ),
    )

    mapping_fork = _mapping(
        mapping_id=previous["security_mapping"]["mapping_id"],
        security_id=previous["security_mapping"]["security_id"],
        listing_id=previous["security_mapping"]["listing_id"],
        symbol="AAA.FORK",
    )
    mapping_event = _transition_event(
        graph, clock, previous, mapping=mapping_fork
    )
    _assert_code(
        "security_mapping_identity_conflict",
        lambda: validate_universe_event_population(
            [*events, mapping_event], universe_id=UNIVERSE_ID
        ),
    )


def test_duplicate_retry_still_requires_the_original_calendar_bound_clock(tmp_path):
    graph, bundle, clock, events = _bound_graph()
    path = tmp_path / "universe.jsonl"
    manifest = _manifest(events, clock)
    _append(path, events, manifest, graph=graph, bundle=bundle, clock=clock)
    later_clock = _clock(
        bundle,
        calendar_session_id="XNYS-2026-08-21",
    )

    _assert_code(
        "manifest_run_clock_mismatch",
        lambda: _append(
            path,
            [],
            manifest,
            graph=graph,
            bundle=bundle,
            clock=later_clock,
        ),
    )


def test_batch_retry_ignores_latest_event_recorded_at_noise(tmp_path):
    graph, bundle, clock, events = _bound_graph()
    path = tmp_path / "universe.jsonl"
    manifest = _manifest(events, clock)
    _append(path, events, manifest, graph=graph, bundle=bundle, clock=clock)

    retry_events = deepcopy(events)
    latest_index = max(
        (
            index
            for index, event in enumerate(retry_events)
            if event["security_mapping"]["security_id"] == "sec-aaa"
        ),
        key=lambda index: retry_events[index]["effective_at"],
    )
    retry_events[latest_index]["recorded_at"] = "2026-08-20T14:11:30Z"
    retry_events[latest_index] = _seal_event(retry_events[latest_index])
    retry_manifest = _manifest(retry_events, clock)

    assert retry_manifest["semantic_hash"] == manifest["semantic_hash"]
    assert retry_manifest["manifest_hash"] != manifest["manifest_hash"]
    retry = _append(
        path,
        [retry_events[latest_index]],
        retry_manifest,
        graph=graph,
        bundle=bundle,
        clock=clock,
    )
    assert retry["status"] == "duplicate"
    loaded = load_v2_universe_ledger(path)
    assert len(loaded["events"]) == len(events)
    assert len(loaded["manifests"]) == 1


def test_manifest_rejects_resealed_missing_membership_and_event_population():
    _, _, clock, events = _bound_graph()
    manifest = _manifest(events, clock)
    missing_membership = deepcopy(manifest)
    missing_membership["memberships"] = missing_membership["memberships"][:-1]
    missing_membership["membership_snapshot_sha256"] = canonical_hash(
        ledger_module._membership_semantic_rows(missing_membership["memberships"])
    )
    missing_membership = _reseal_manifest(missing_membership)
    _assert_code(
        "manifest_membership_mismatch",
        lambda: validate_universe_membership_manifest(
            missing_membership,
            events=events,
            run_clock=clock,
            effective_clock=clock,
        ),
    )

    missing_event = deepcopy(manifest)
    missing_event["universe_event_ids"] = missing_event["universe_event_ids"][:-1]
    missing_event = _reseal_manifest(missing_event)
    _assert_code(
        "manifest_event_population_mismatch",
        lambda: validate_universe_membership_manifest(
            missing_event,
            events=events,
            run_clock=clock,
            effective_clock=clock,
        ),
    )


def test_population_rejects_broken_chain_mixed_universe_and_future_event():
    _, _, _, events = _bound_graph()
    broken = deepcopy(events)
    transition_index = next(
        index
        for index, event in enumerate(broken)
        if event["event_type"] == "state_transition"
    )
    transition = broken[transition_index]
    transition["previous_event_hash"] = "0" * 64
    broken[transition_index] = _seal_event(transition)
    _assert_code(
        "broken_universe_event_chain",
        lambda: validate_universe_event_population(broken, universe_id=UNIVERSE_ID),
    )

    mixed = deepcopy(events)
    mixed[0]["universe_id"] = "another-universe"
    mixed[0] = _seal_event(mixed[0])
    _assert_code(
        "mixed_universe_population",
        lambda: validate_universe_event_population(mixed, universe_id=UNIVERSE_ID),
    )

    _assert_code(
        "universe_event_after_cutoff",
        lambda: validate_universe_event_population(
            events,
            universe_id=UNIVERSE_ID,
            data_cutoff="2026-08-20T14:05:59Z",
        ),
    )


def test_second_manifest_preserves_history_and_replay_uses_explicit_commit(tmp_path):
    graph, bundle, clock, events = _bound_graph(quarantine_second=False)
    path = tmp_path / "universe.jsonl"
    first = _manifest(events, clock)
    _append(path, events, first, graph=graph, bundle=bundle, clock=clock)

    previous = max(
        (
            event
            for event in events
            if event["security_mapping"]["security_id"] == "sec-aaa"
        ),
        key=lambda event: event["effective_at"],
    )
    transition = _transition_event(graph, clock, previous)
    all_events = events + [transition]
    second = _manifest(
        all_events,
        clock,
        previous=first,
        suffix="2",
        membership_as_of="2026-08-20T14:26:00Z",
        data_cutoff="2026-08-20T14:26:00Z",
        frozen_at="2026-08-20T14:27:00Z",
        recorded_at="2026-08-20T14:28:00Z",
    )
    result = _append(
        path,
        [transition],
        second,
        graph=graph,
        bundle=bundle,
        clock=clock,
    )

    assert result["status"] == "appended"
    loaded = load_v2_universe_ledger(path)
    assert len(loaded["manifests"]) == 2
    first_view = read_v2_universe_membership(
        path,
        manifest_id=first["manifest_id"],
        as_of=first["membership_as_of"],
    )
    second_view = read_v2_universe_membership(
        path,
        manifest_id=second["manifest_id"],
        as_of=second["membership_as_of"],
    )
    first_aaa = next(
        row for row in first_view["memberships"] if row["security_id"] == "sec-aaa"
    )
    second_aaa = next(
        row for row in second_view["memberships"] if row["security_id"] == "sec-aaa"
    )
    assert first_aaa["state"] == "candidate_eligible"
    assert second_aaa["state"] == "quarantine"


def test_future_effective_event_is_frozen_before_it_changes_membership(tmp_path):
    graph, bundle, clock, events = _bound_graph(quarantine_second=False)
    path = tmp_path / "universe.jsonl"
    first = _manifest(events, clock)
    _append(path, events, first, graph=graph, bundle=bundle, clock=clock)
    previous = max(
        (
            event
            for event in events
            if event["security_mapping"]["security_id"] == "sec-aaa"
        ),
        key=lambda event: event["effective_at"],
    )
    future_clock = _clock(
        bundle,
        calendar_session_id="XNYS-2026-08-21",
        assignment_cutoff="2026-08-20T14:20:00Z",
        frozen_at="2026-08-20T14:21:00Z",
        recorded_at="2026-08-20T14:22:00Z",
    )
    transition = _transition_event(
        graph,
        clock,
        previous,
        effective_clock=future_clock,
        effective_at="2026-08-21T13:30:00Z",
    )
    all_events = events + [transition]
    scheduled = _manifest(
        all_events,
        clock,
        previous=first,
        suffix="2",
        effective_clock=future_clock,
        membership_as_of="2026-08-20T14:24:00Z",
        data_cutoff="2026-08-20T14:24:00Z",
        frozen_at="2026-08-20T14:25:00Z",
        recorded_at="2026-08-20T14:26:00Z",
    )
    _append(
        path,
        [transition],
        scheduled,
        graph=graph,
        bundle=bundle,
        clock=clock,
        effective_clock=future_clock,
    )
    scheduled_view = read_v2_universe_membership(
        path,
        manifest_id=scheduled["manifest_id"],
        as_of=scheduled["membership_as_of"],
    )
    assert next(
        row for row in scheduled_view["memberships"] if row["security_id"] == "sec-aaa"
    )["state"] == "candidate_eligible"

    activated = _manifest(
        all_events,
        future_clock,
        previous=scheduled,
        suffix="3",
        membership_as_of="2026-08-21T14:00:00Z",
        data_cutoff="2026-08-21T14:00:00Z",
        frozen_at="2026-08-21T14:01:00Z",
        recorded_at="2026-08-21T14:02:00Z",
    )
    _append(
        path,
        [],
        activated,
        graph=graph,
        bundle=bundle,
        clock=future_clock,
    )
    activated_view = read_v2_universe_membership(
        path,
        manifest_id=activated["manifest_id"],
        as_of=activated["membership_as_of"],
    )
    assert next(
        row for row in activated_view["memberships"] if row["security_id"] == "sec-aaa"
    )["state"] == "quarantine"


def test_manifest_chain_rejects_retroactive_events_and_prefrozen_successor():
    graph, _, clock, events = _bound_graph(quarantine_second=False)
    first = _manifest(events, clock)
    previous = max(
        (
            event
            for event in events
            if event["security_mapping"]["security_id"] == "sec-aaa"
        ),
        key=lambda event: event["effective_at"],
    )
    retroactive = _transition_event(
        graph,
        clock,
        previous,
        decided_at="2026-08-20T14:19:00Z",
        recorded_at="2026-08-20T14:23:00Z",
    )
    _assert_code(
        "retroactive_universe_event",
        lambda: _manifest(
            events + [retroactive],
            clock,
            previous=first,
            suffix="2",
            membership_as_of="2026-08-20T14:26:00Z",
            data_cutoff="2026-08-20T14:26:00Z",
            frozen_at="2026-08-20T14:27:00Z",
            recorded_at="2026-08-20T14:28:00Z",
        ),
    )
    _assert_code(
        "nonmonotonic_manifest_chain",
        lambda: _manifest(
            events,
            clock,
            previous=first,
            suffix="causal",
            data_cutoff="2026-08-20T14:21:00Z",
            frozen_at="2026-08-20T14:21:00Z",
            recorded_at="2026-08-20T14:23:00Z",
        ),
    )


def test_loader_rejects_resealed_pit_upgrade(tmp_path):
    graph, bundle, clock, events = _bound_graph()
    path = tmp_path / "universe.jsonl"
    manifest = _manifest(events, clock)
    _append(path, events, manifest, graph=graph, bundle=bundle, clock=clock)
    rows = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(rows[-1])
    tampered["pit_tier"] = "canonical_pit"
    rows[-1] = ledger_module.canonical_json(_reseal_manifest(tampered))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    _assert_code(
        "research_pit_ceiling_required", lambda: load_v2_universe_ledger(path)
    )


def test_loader_rejects_resealed_cross_manifest_clock_id_alias(tmp_path):
    graph, bundle, clock, _ = _bound_graph()
    path = tmp_path / "universe.jsonl"
    first = _manifest([], clock, suffix="empty-1")
    _append(path, [], first, graph=graph, bundle=bundle, clock=clock)
    later_clock = _clock(bundle, calendar_session_id="XNYS-2026-08-21")
    second = _manifest(
        [],
        later_clock,
        previous=first,
        suffix="empty-2",
        membership_as_of="2026-08-21T14:00:00Z",
        data_cutoff="2026-08-21T14:00:00Z",
        frozen_at="2026-08-21T14:01:00Z",
        recorded_at="2026-08-21T14:02:00Z",
    )
    _append(
        path,
        [],
        second,
        graph=graph,
        bundle=bundle,
        clock=later_clock,
    )
    rows = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(rows[-1])
    tampered["session_clock_id"] = first["session_clock_id"]
    rows[-1] = ledger_module.canonical_json(_reseal_manifest(tampered))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    _assert_code(
        "damaged_session_clock_registry", lambda: load_v2_universe_ledger(path)
    )


def test_loader_rejects_resealed_same_manifest_clock_id_alias(tmp_path):
    graph, bundle, clock, _ = _bound_graph()
    path = tmp_path / "universe.jsonl"
    effective_clock = _clock(
        bundle,
        calendar_session_id="XNYS-2026-08-21",
        assignment_cutoff="2026-08-20T14:18:00Z",
        frozen_at="2026-08-20T14:18:30Z",
        recorded_at="2026-08-20T14:19:00Z",
    )
    manifest = _manifest(
        [],
        clock,
        suffix="same-manifest-clock-alias",
        effective_clock=effective_clock,
    )
    _append(
        path,
        [],
        manifest,
        graph=graph,
        bundle=bundle,
        clock=clock,
        effective_clock=effective_clock,
    )
    rows = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(rows[-1])
    tampered["effective_session_clock_id"] = tampered["session_clock_id"]
    rows[-1] = ledger_module.canonical_json(_reseal_manifest(tampered))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    _assert_code(
        "damaged_session_clock_registry", lambda: load_v2_universe_ledger(path)
    )


@pytest.mark.parametrize("with_events", (False, True))
def test_loader_rejects_resealed_clock_calendar_evidence_pruning(
    tmp_path, with_events
):
    graph, bundle, clock, events = _bound_graph()
    committed_events = events if with_events else []
    path = tmp_path / "universe.jsonl"
    manifest = _manifest(
        committed_events,
        clock,
        suffix="1" if with_events else "calendar-prune-empty",
    )
    _append(
        path,
        committed_events,
        manifest,
        graph=graph,
        bundle=bundle,
        clock=clock,
    )
    rows = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(rows[-1])
    evidence_id = clock["calendar_evidence_id"]
    evidence_binding = tampered["evidence_record_registry"].pop(evidence_id)
    source_id = evidence_binding["source_contract_id"]
    assert not any(
        binding["source_contract_id"] == source_id
        for binding in tampered["evidence_record_registry"].values()
    )
    tampered["source_contract_registry"].pop(source_id)
    rows[-1] = ledger_module.canonical_json(_reseal_manifest(tampered))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    _assert_code(
        "missing_clock_calendar_evidence", lambda: load_v2_universe_ledger(path)
    )


def test_writer_rejects_event_batch_id_reuse_across_full_history(tmp_path):
    graph, bundle, clock, events = _bound_graph()
    path = tmp_path / "universe.jsonl"
    first = _manifest(events, clock)
    _append(path, events, first, graph=graph, bundle=bundle, clock=clock)
    second = _manifest(
        events,
        clock,
        previous=first,
        suffix="2",
        data_cutoff="2026-08-20T14:21:00Z",
        frozen_at="2026-08-20T14:22:00Z",
        recorded_at="2026-08-20T14:23:00Z",
    )
    _append(path, [], second, graph=graph, bundle=bundle, clock=clock)
    reused = _manifest(
        events,
        clock,
        previous=second,
        suffix="3",
        event_batch_id=first["event_batch_id"],
        data_cutoff="2026-08-20T14:22:00Z",
        frozen_at="2026-08-20T14:23:00Z",
        recorded_at="2026-08-20T14:24:00Z",
    )

    _assert_code(
        "event_batch_id_conflict",
        lambda: _append(
            path,
            [],
            reused,
            graph=graph,
            bundle=bundle,
            clock=clock,
        ),
    )
    assert len(load_v2_universe_ledger(path)["manifests"]) == 2


def test_loader_rejects_orphan_tail_unknown_row_and_damaged_prefix(tmp_path):
    graph, bundle, clock, events = _bound_graph()
    path = tmp_path / "universe.jsonl"
    manifest = _manifest(events, clock)
    _append(path, events, manifest, graph=graph, bundle=bundle, clock=clock)
    original = path.read_text(encoding="utf-8")

    path.write_text(original + ledger_module.canonical_json(events[0]) + "\n", encoding="utf-8")
    _assert_code("duplicate_physical_universe_event", lambda: load_v2_universe_ledger(path))

    changed = deepcopy(events[0])
    changed["reason"] = "Same immutable event ID with changed semantics."
    changed = _seal_event(changed)
    path.write_text(original + ledger_module.canonical_json(changed) + "\n", encoding="utf-8")
    _assert_code("immutable_key_conflict", lambda: load_v2_universe_ledger(path))

    path.write_text(original + '{"record_type":"unknown"}\n', encoding="utf-8")
    _assert_code("unsupported_ledger_record_type", lambda: load_v2_universe_ledger(path))

    rows = original.splitlines()
    damaged = __import__("json").loads(rows[0])
    damaged["reason"] = "tampered without resealing"
    rows[0] = ledger_module.canonical_json(damaged)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    _assert_code("semantic_hash_mismatch", lambda: load_v2_universe_ledger(path))


def test_atomic_failure_leaves_no_partial_transaction(tmp_path, monkeypatch):
    graph, bundle, clock, events = _bound_graph()
    path = tmp_path / "universe.jsonl"
    manifest = _manifest(events, clock)

    def fail_write(text, filepath):
        raise OSError("synthetic atomic replace failure")

    monkeypatch.setattr(ledger_module, "atomic_write_text", fail_write)
    with pytest.raises(OSError, match="synthetic"):
        _append(
            path,
            events,
            manifest,
            graph=graph,
            bundle=bundle,
            clock=clock,
        )
    assert not path.exists()


def test_concurrent_same_batch_commits_once_without_duplicate_rows(tmp_path):
    graph, bundle, clock, events = _bound_graph()
    path = tmp_path / "universe.jsonl"
    manifest = _manifest(events, clock)

    def append_once(_):
        return _append(
            path,
            events,
            manifest,
            graph=graph,
            bundle=bundle,
            clock=clock,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(append_once, range(2)))
    assert sorted(item["status"] for item in results) == ["appended", "duplicate"]
    loaded = load_v2_universe_ledger(path)
    assert len(loaded["events"]) == len(events)
    assert len(loaded["manifests"]) == 1


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        ("trade_enabled", True, "trade_enabled_forbidden"),
        (
            "ledger_population_complete",
            False,
            "complete_ledger_population_required",
        ),
        ("paper_live_eligible", True, "paper_live_eligible_forbidden"),
        (
            "external_universe_coverage_status",
            "verified",
            "external_universe_coverage_unverified",
        ),
        ("known_future_leakage", True, "future_leakage_forbidden"),
        ("authority", "trading", "research_authority_required"),
    ),
)
def test_manifest_default_off_and_completeness_fields_fail_closed(field, value, code):
    _, _, clock, events = _bound_graph()
    manifest = _manifest(events, clock)
    manifest[field] = value
    manifest = _reseal_manifest(manifest)
    _assert_code(
        code,
        lambda: validate_universe_membership_manifest(
            manifest,
            events=events,
            run_clock=clock,
            effective_clock=clock,
        ),
    )


@pytest.mark.parametrize("timeout", (-1, 1))
def test_writer_request_validation_precedes_timeout_and_ledger_io(tmp_path, timeout):
    graph, bundle, clock, events = _bound_graph()
    manifest = _manifest(events, clock)
    path = tmp_path / f"damaged-{timeout}.jsonl"
    path.write_text("{", encoding="utf-8")

    _assert_code(
        "event_sequence_required",
        lambda: _append(
            path,
            "not-an-event-sequence",
            manifest,
            graph=graph,
            bundle=bundle,
            clock=clock,
            lock_timeout_seconds=timeout,
        ),
    )
    assert path.read_text(encoding="utf-8") == "{"
