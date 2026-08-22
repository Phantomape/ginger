from copy import deepcopy
from dataclasses import replace

import pytest

from quant.test_v2_contracts import _assert_code, _evidence, _mapping, _source
from quant.test_v2_research_contracts import (
    _graph,
    _pool,
    _seal_pool,
    _validate_graph,
)
from quant.v2_contracts import (
    DecisionRecord,
    OrderIntent,
    ReplacementValue,
    SettledOutcome,
    candidate_pool_input_snapshot_hash,
    canonical_hash,
    decision_input_snapshot_hash,
    normalize_decision_record,
    normalize_order_intent,
    normalize_replacement_value,
    normalize_settled_outcome,
    order_intent_input_snapshot_hash,
    replacement_value_input_snapshot_hash,
    replacement_value_stable_key,
    settlement_evidence_snapshot_hash,
    settled_outcome_input_snapshot_hash,
    settled_outcome_stable_key,
    validate_decision_record,
    validate_decision_record_against_candidate_pool,
    validate_order_intent,
    validate_order_intent_against_decision,
    validate_replacement_value,
    validate_replacement_value_against_inputs,
    validate_replacement_value_panel,
    validate_settled_outcome,
    validate_settled_outcome_against_inputs,
)


def _seal(row, *, list_fields=(), nested_sort=None):
    row = deepcopy(row)
    for field in list_fields:
        row[field] = sorted(row[field])
    if nested_sort is not None:
        field, key = nested_sort
        row[field] = sorted(row[field], key=lambda item: item[key])
    row.pop("semantic_hash", None)
    row.pop("record_hash", None)
    semantic = deepcopy(row)
    semantic.pop("recorded_at")
    row["semantic_hash"] = canonical_hash(semantic)
    record = deepcopy(row)
    row["record_hash"] = canonical_hash(record)
    return row


def _decision(graph, **overrides):
    pool = graph["pool"]
    measurement_pit_tier = (
        "research_pit" if pool["pit_tier"] == "canonical_pit" else pool["pit_tier"]
    )
    measurement_result_ceiling = (
        "observed_only"
        if measurement_pit_tier == "research_pit"
        else pool["result_ceiling"]
    )
    admitted_rank = 0
    items = []
    for entry in sorted(pool["entries"], key=lambda item: item["candidate_entry_id"]):
        admitted = entry["admission_status"] == "admitted"
        if admitted:
            admitted_rank += 1
        selected = admitted and admitted_rank == 1
        items.append(
            {
                "decision_item_id": f"decision-item-{entry['candidate_entry_id']}",
                "candidate_entry_id": entry["candidate_entry_id"],
                "security_id": entry["security_id"],
                "listing_id": entry["listing_id"],
                "security_mapping_sha256": entry["security_mapping_sha256"],
                "rank": admitted_rank if admitted else None,
                "signal_action": "selected" if selected else ("not_selected" if admitted else None),
                "side": "buy" if selected else None,
                "risk_status": "approved" if selected else None,
                "approved_quantity_micros": None,
                "approved_notional_minor": 100_000 if selected else None,
                "currency": "USD" if selected else None,
                "reason_code": "selected_by_frozen_policy" if selected else "not_selected",
                "reason": "Deterministic research-only decision over the complete pool.",
            }
        )
    row = {
        "schema_version": 2,
        "record_type": "v2_decision_record",
        "decision_id": "decision-20260820-v1",
        "candidate_pool_id": pool["candidate_pool_id"],
        "candidate_pool_hash": pool["semantic_hash"],
        "candidate_pool_record_hash": pool["record_hash"],
        "policy_arm": "treatment",
        "policy_snapshot": graph["hypothesis"]["treatment_policy"],
        "decision_engine_id": "v2-deterministic-research-engine",
        "decision_engine_version": "1",
        "decision_engine_sha256": "b" * 64,
        "decision_context_id": "decision-context-20260820-v1",
        "decision_context_sha256": "c" * 64,
        "execution_rule_id": "research-intent-rule",
        "execution_rule_version": "1",
        "execution_rule_sha256": "d" * 64,
        "cost_rule_id": "frozen-cost-rule",
        "cost_rule_version": graph["hypothesis"]["treatment_policy"][
            "cost_policy_version"
        ],
        "cost_rule_sha256": "1" * 64,
        "comparison_rule_id": "frozen-replacement-rule",
        "comparison_rule_version": "1",
        "comparison_rule_sha256": "2" * 64,
        "items": items,
        "expected_item_count": len(items),
        "decision_complete": True,
        "run_id": pool["run_id"],
        "session_clock_id": pool["session_clock_id"],
        "session_clock_hash": pool["session_clock_hash"],
        "session_clock_record_hash": pool["session_clock_record_hash"],
        "run_date": pool["run_date"],
        "calendar_session_id": pool["calendar_session_id"],
        "data_cutoff": pool["data_cutoff"],
        "expected_horizon": graph["hypothesis"]["expected_horizon"],
        "decided_at": "2026-08-20T14:15:00Z",
        "recorded_at": "2026-08-20T14:16:00Z",
        "input_snapshot_sha256": "0" * 64,
        "pit_tier": measurement_pit_tier,
        "result_ceiling": measurement_result_ceiling,
        "known_future_leakage": pool["known_future_leakage"],
        "outcome_blind": True,
        "results_accessed": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    row.update(overrides)
    row["input_snapshot_sha256"] = decision_input_snapshot_hash(
        candidate_pool=pool,
        policy_arm=row["policy_arm"],
        policy_snapshot=row["policy_snapshot"],
        decision_engine_id=row["decision_engine_id"],
        decision_engine_version=row["decision_engine_version"],
        decision_engine_sha256=row["decision_engine_sha256"],
        decision_context_id=row["decision_context_id"],
        decision_context_sha256=row["decision_context_sha256"],
        execution_rule_id=row["execution_rule_id"],
        execution_rule_version=row["execution_rule_version"],
        execution_rule_sha256=row["execution_rule_sha256"],
        cost_rule_id=row["cost_rule_id"],
        cost_rule_version=row["cost_rule_version"],
        cost_rule_sha256=row["cost_rule_sha256"],
        comparison_rule_id=row["comparison_rule_id"],
        comparison_rule_version=row["comparison_rule_version"],
        comparison_rule_sha256=row["comparison_rule_sha256"],
        items=row["items"],
        run_id=row["run_id"],
        session_clock_id=row["session_clock_id"],
        session_clock_hash=row["session_clock_hash"],
        session_clock_record_hash=row["session_clock_record_hash"],
        run_date=row["run_date"],
        calendar_session_id=row["calendar_session_id"],
        data_cutoff=row["data_cutoff"],
        expected_horizon=row["expected_horizon"],
    )
    return _seal(row, nested_sort=("items", "candidate_entry_id"))


def _intent(decision, **overrides):
    selected = next(
        item
        for item in decision["items"]
        if item["signal_action"] == "selected" and item["risk_status"] == "approved"
    )
    row = {
        "schema_version": 2,
        "record_type": "v2_order_intent",
        "order_intent_id": "intent-20260820-v1",
        "decision_id": decision["decision_id"],
        "decision_hash": decision["semantic_hash"],
        "decision_record_hash": decision["record_hash"],
        "decision_item_id": selected["decision_item_id"],
        "candidate_entry_id": selected["candidate_entry_id"],
        "security_id": selected["security_id"],
        "listing_id": selected["listing_id"],
        "security_mapping_sha256": selected["security_mapping_sha256"],
        "side": "buy",
        "quantity_micros": selected["approved_quantity_micros"],
        "notional_minor": selected["approved_notional_minor"],
        "currency": selected["currency"],
        "order_type": "limit",
        "limit_price_minor": 10_000,
        "stop_price_minor": None,
        "time_in_force": "day",
        "not_before": "2026-08-20T14:19:00Z",
        "expires_at": "2026-08-20T14:30:00Z",
        "calendar_session_id": decision["calendar_session_id"],
        "session_clock_id": decision["session_clock_id"],
        "session_clock_hash": decision["session_clock_hash"],
        "session_clock_record_hash": decision["session_clock_record_hash"],
        "execution_rule_id": decision["execution_rule_id"],
        "execution_rule_version": decision["execution_rule_version"],
        "execution_rule_sha256": decision["execution_rule_sha256"],
        "created_at": "2026-08-20T14:17:00Z",
        "recorded_at": "2026-08-20T14:18:00Z",
        "input_snapshot_sha256": "0" * 64,
        "submitted": False,
        "authority": "research_only",
        "trade_enabled": False,
    }
    row.update(overrides)
    row["input_snapshot_sha256"] = order_intent_input_snapshot_hash(
        decision_record=decision,
        decision_item_id=row["decision_item_id"],
        side=row["side"],
        quantity_micros=row["quantity_micros"],
        notional_minor=row["notional_minor"],
        currency=row["currency"],
        order_type=row["order_type"],
        limit_price_minor=row["limit_price_minor"],
        stop_price_minor=row["stop_price_minor"],
        time_in_force=row["time_in_force"],
        not_before=row["not_before"],
        expires_at=row["expires_at"],
        calendar_session_id=row["calendar_session_id"],
        session_clock_id=row["session_clock_id"],
        session_clock_hash=row["session_clock_hash"],
        session_clock_record_hash=row["session_clock_record_hash"],
        execution_rule_id=row["execution_rule_id"],
        execution_rule_version=row["execution_rule_version"],
        execution_rule_sha256=row["execution_rule_sha256"],
        created_at=row["created_at"],
    )
    return _seal(row)


def _measurement_evidence(graph, suffix, *, source=None, minute=31, **overrides):
    source = graph["source"] if source is None else source
    published = f"2026-08-20T15:{minute - 1:02d}:00Z"
    known = f"2026-08-20T15:{minute:02d}:00Z"
    recorded = f"2026-08-20T15:{minute + 1:02d}:00Z"
    decision_content = overrides.pop(
        "decision_content",
        {"event_state": "settled", "published_at": published},
    )
    return _evidence(
        source=source,
        evidence_id=f"measurement-evidence-{suffix}-r1",
        raw_identity={"event_id": f"measurement-{suffix}", "revision_id": "r1"},
        raw_artifact_locator=f"raw/measurement/{suffix}-r1.json",
        raw_artifact_sha256=f"{(int(suffix, 16) % 15) + 1:x}" * 64,
        decision_content=decision_content,
        observed_at=known,
        published_at=published,
        known_at=known,
        effective_from=published,
        recorded_at=recorded,
        **overrides,
    )


def _outcome(decision, intent, evidence, *, status="settled", **overrides):
    unavailable = status == "unavailable"
    row = {
        "schema_version": 1,
        "record_type": "v2_settled_outcome",
        "outcome_id": "outcome-intent-20260820-r1",
        "stable_key": settled_outcome_stable_key(
            order_intent_id=intent["order_intent_id"], horizon="one-session"
        ),
        "revision_number": 1,
        "previous_outcome_id": None,
        "previous_outcome_record_hash": None,
        "decision_id": decision["decision_id"],
        "decision_hash": decision["semantic_hash"],
        "decision_record_hash": decision["record_hash"],
        "order_intent_id": intent["order_intent_id"],
        "order_intent_hash": intent["semantic_hash"],
        "order_intent_record_hash": intent["record_hash"],
        "candidate_pool_id": decision["candidate_pool_id"],
        "candidate_pool_hash": decision["candidate_pool_hash"],
        "candidate_pool_record_hash": decision["candidate_pool_record_hash"],
        "fill_snapshot_id": "fill-snapshot-synthetic-v1",
        "fill_snapshot_sha256": "e" * 64,
        "position_snapshot_id": "position-snapshot-synthetic-v1",
        "position_snapshot_sha256": "f" * 64,
        "settlement_evidence_record_ids": [item["evidence_id"] for item in evidence],
        "settlement_evidence_snapshot_sha256": settlement_evidence_snapshot_hash(evidence),
        "horizon": decision["expected_horizon"],
        "entry_session_id": intent["calendar_session_id"],
        "entry_at": "2026-08-20T14:20:00Z",
        "exit_session_id": "XNYS-2026-08-20-close",
        "exit_at": "2026-08-20T15:30:00Z",
        "settled_at": "2026-08-20T15:33:00Z",
        "recorded_at": "2026-08-20T15:34:00Z",
        "status": status,
        "reason_code": "measurement_unavailable" if unavailable else "measurement_settled",
        "reason": "Synthetic measurement row for contract verification.",
        "basis_notional_minor": None if unavailable else intent["notional_minor"],
        "currency": None if unavailable else intent["currency"],
        "gross_pnl_minor": None if unavailable else 12_000,
        "cost_minor": None if unavailable else 2_000,
        "net_pnl_minor": None if unavailable else 10_000,
        "cost_rule_id": decision["cost_rule_id"],
        "cost_rule_version": decision["cost_rule_version"],
        "cost_rule_sha256": decision["cost_rule_sha256"],
        "comparison_rule_id": decision["comparison_rule_id"],
        "comparison_rule_version": decision["comparison_rule_version"],
        "comparison_rule_sha256": decision["comparison_rule_sha256"],
        "input_snapshot_sha256": "0" * 64,
        "pit_tier": decision["pit_tier"],
        "result_ceiling": decision["result_ceiling"],
        "known_future_leakage": decision["known_future_leakage"],
        "measurement_only": True,
        "trade_enabled": False,
    }
    row.update(overrides)
    row["stable_key"] = settled_outcome_stable_key(
        order_intent_id=row["order_intent_id"], horizon=row["horizon"]
    )
    row["input_snapshot_sha256"] = settled_outcome_input_snapshot_hash(
        decision_record=decision,
        order_intent=intent,
        settlement_evidence_records=evidence,
        fill_snapshot_id=row["fill_snapshot_id"],
        fill_snapshot_sha256=row["fill_snapshot_sha256"],
        position_snapshot_id=row["position_snapshot_id"],
        position_snapshot_sha256=row["position_snapshot_sha256"],
        horizon=row["horizon"],
        entry_session_id=row["entry_session_id"],
        entry_at=row["entry_at"],
        exit_session_id=row["exit_session_id"],
        exit_at=row["exit_at"],
        cost_rule_id=row["cost_rule_id"],
        cost_rule_version=row["cost_rule_version"],
        cost_rule_sha256=row["cost_rule_sha256"],
        comparison_rule_id=row["comparison_rule_id"],
        comparison_rule_version=row["comparison_rule_version"],
        comparison_rule_sha256=row["comparison_rule_sha256"],
    )
    return _seal(row, list_fields=("settlement_evidence_record_ids",))


def _replacement(outcome, pool, evidence, role, *, status="computed", **overrides):
    comparator = next(item for item in pool["comparators"] if item["role"] == role)
    unavailable = status == "unavailable"
    comparator_values = {"cash": 0, "spy": 500, "qqq": -200, "v1": 1_000}
    strategy = None if unavailable else outcome["net_pnl_minor"]
    comparator_value = None if unavailable else comparator_values[role]
    row = {
        "schema_version": 1,
        "record_type": "v2_replacement_value",
        "replacement_value_id": f"replacement-{role}-r{outcome['revision_number']}",
        "stable_key": replacement_value_stable_key(
            settled_outcome_stable_key=outcome["stable_key"], comparator_role=role
        ),
        "revision_number": outcome["revision_number"],
        "previous_replacement_value_id": None,
        "previous_replacement_value_record_hash": None,
        "settled_outcome_id": outcome["outcome_id"],
        "settled_outcome_hash": outcome["semantic_hash"],
        "settled_outcome_record_hash": outcome["record_hash"],
        "candidate_pool_id": pool["candidate_pool_id"],
        "candidate_pool_hash": pool["semantic_hash"],
        "candidate_pool_record_hash": pool["record_hash"],
        "comparator_role": role,
        "comparator_reference_id": comparator["reference_id"],
        "comparator_reference_snapshot_sha256": comparator["reference_snapshot_sha256"],
        "comparator_evidence_record_ids": [item["evidence_id"] for item in evidence],
        "comparator_evidence_snapshot_sha256": settlement_evidence_snapshot_hash(
            evidence
        ),
        "comparison_rule_id": outcome["comparison_rule_id"],
        "comparison_rule_version": outcome["comparison_rule_version"],
        "comparison_rule_sha256": outcome["comparison_rule_sha256"],
        "status": status,
        "reason_code": "comparator_unavailable" if unavailable else "comparison_computed",
        "reason": "Synthetic comparator measurement for contract verification.",
        "basis_notional_minor": None if unavailable else outcome["basis_notional_minor"],
        "currency": None if unavailable else outcome["currency"],
        "strategy_value_minor": strategy,
        "comparator_value_minor": comparator_value,
        "replacement_value_minor": (
            None if unavailable else strategy - comparator_value
        ),
        "settled_at": "2026-08-20T15:38:00Z",
        "recorded_at": "2026-08-20T15:39:00Z",
        "input_snapshot_sha256": "0" * 64,
        "pit_tier": outcome["pit_tier"],
        "result_ceiling": outcome["result_ceiling"],
        "known_future_leakage": outcome["known_future_leakage"],
        "measurement_only": True,
        "trade_enabled": False,
    }
    row.update(overrides)
    row["stable_key"] = replacement_value_stable_key(
        settled_outcome_stable_key=outcome["stable_key"],
        comparator_role=row["comparator_role"],
    )
    row["input_snapshot_sha256"] = replacement_value_input_snapshot_hash(
        settled_outcome=outcome,
        candidate_pool=pool,
        comparator=comparator,
        comparator_evidence_records=evidence,
        comparison_rule_id=row["comparison_rule_id"],
        comparison_rule_version=row["comparison_rule_version"],
        comparison_rule_sha256=row["comparison_rule_sha256"],
    )
    return _seal(row, list_fields=("comparator_evidence_record_ids",))


def _chain(*, two_candidates=False):
    graph = _graph(two_candidates=two_candidates)
    spy_mapping = _mapping(
        mapping_id="map-sec-spy-arcx-v1",
        security_id="sec-spy",
        listing_id="listing-spy-arcx",
        symbol="SPY",
        mic="ARCX",
    )
    qqq_mapping = _mapping(
        mapping_id="map-sec-qqq-xnas-v1",
        security_id="sec-qqq",
        listing_id="listing-qqq-xnas",
        symbol="QQQ",
        mic="XNAS",
    )
    pool = deepcopy(graph["pool"])
    comparator_mappings = {"spy": spy_mapping, "qqq": qqq_mapping}
    for comparator in pool["comparators"]:
        mapping = comparator_mappings.get(comparator["role"])
        if mapping is not None:
            comparator["reference_snapshot_sha256"] = mapping["mapping_sha256"]
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
    graph["pool"] = _seal_pool(pool)

    decision = _decision(graph)
    intent = _intent(decision)
    settlement_evidence = [_measurement_evidence(graph, "8")]
    outcome = _outcome(decision, intent, settlement_evidence)
    comparator_content_fields = [
        "event_state",
        "published_at",
        "comparator_reference_id",
        "comparator_reference_snapshot_sha256",
    ]
    instrument_comparator_source = _source(
        source_contract_id="source-instrument-comparators-v1",
        source_name="instrument_comparator_feed",
        source_locator="https://agency.example/instrument-comparators",
        decision_content_fields=comparator_content_fields,
    )
    non_security_source = _source(
        source_contract_id="source-non-security-comparators-v1",
        source_name="non_security_comparator_feed",
        source_locator="https://agency.example/non-security-comparators",
        decision_content_fields=comparator_content_fields,
        security_mapping_policy="not_applicable",
    )
    comparators = {item["role"]: item for item in graph["pool"]["comparators"]}

    def comparator_content(role):
        comparator = comparators[role]
        return {
            "event_state": "settled",
            "published_at": "2026-08-20T15:34:00Z",
            "comparator_reference_id": comparator["reference_id"],
            "comparator_reference_snapshot_sha256": comparator[
                "reference_snapshot_sha256"
            ],
        }

    comparator_evidence = [
        _measurement_evidence(
            graph,
            "9",
            source=non_security_source,
            minute=35,
            security_scope="not_applicable",
            security_mapping_kind="not_applicable",
            security_mapping=None,
            decision_content=comparator_content("cash"),
        ),
        _measurement_evidence(
            graph,
            "a",
            source=instrument_comparator_source,
            minute=35,
            security_mapping=spy_mapping,
            decision_content=comparator_content("spy"),
        ),
        _measurement_evidence(
            graph,
            "b",
            source=instrument_comparator_source,
            minute=35,
            security_mapping=qqq_mapping,
            decision_content=comparator_content("qqq"),
        ),
        _measurement_evidence(
            graph,
            "c",
            source=non_security_source,
            minute=35,
            security_scope="not_applicable",
            security_mapping_kind="not_applicable",
            security_mapping=None,
            decision_content=comparator_content("v1"),
        ),
    ]
    graph["measurement_sources"] = [
        graph["source"],
        instrument_comparator_source,
        non_security_source,
    ]
    replacements = [
        _replacement(outcome, graph["pool"], [evidence], role)
        for evidence, role in zip(
            comparator_evidence, ("cash", "spy", "qqq", "v1")
        )
    ]
    return graph, decision, intent, settlement_evidence, outcome, comparator_evidence, replacements


def _swap_decision_item_security_identities(row):
    fields = ("security_id", "listing_id", "security_mapping_sha256")
    left = {field: row["items"][0][field] for field in fields}
    right = {field: row["items"][1][field] for field in fields}
    row["items"][0].update(right)
    row["items"][1].update(left)


def test_round_trip_immutability_and_recorded_at_hash_semantics():
    graph, decision, intent, _, outcome, _, replacements = _chain()
    records = (
        (validate_decision_record, normalize_decision_record, decision, DecisionRecord),
        (validate_order_intent, normalize_order_intent, intent, OrderIntent),
        (validate_settled_outcome, normalize_settled_outcome, outcome, SettledOutcome),
        (
            validate_replacement_value,
            normalize_replacement_value,
            replacements[0],
            ReplacementValue,
        ),
    )
    for validator, normalizer, row, expected_type in records:
        original = deepcopy(row)
        record = validator(row)
        assert row == original
        assert isinstance(record, expected_type)
        assert normalizer(record) == normalizer(row)
        assert record.canonical_hash == canonical_hash(record.to_dict())
        later = deepcopy(row)
        later["recorded_at"] = later["recorded_at"].replace(":00Z", ":30Z")
        later = _seal(
            later,
            list_fields=(
                "settlement_evidence_record_ids"
                if "settlement_evidence_record_ids" in later
                else "comparator_evidence_record_ids"
                if "comparator_evidence_record_ids" in later
                else "unused",
            ) if "settlement_evidence_record_ids" in later or "comparator_evidence_record_ids" in later else (),
            nested_sort=("items", "candidate_entry_id") if "items" in later else None,
        )
        assert later["semantic_hash"] == row["semantic_hash"]
        assert later["record_hash"] != row["record_hash"]
    frozen = validate_decision_record_against_candidate_pool(
        decision, graph["pool"], graph["hypothesis"]
    )
    with pytest.raises(TypeError):
        frozen.policy_snapshot["policy_id"] = "changed"
    with pytest.raises(AttributeError):
        frozen.items[0].rank = 9


def test_decision_exactly_covers_full_pool_and_supports_explicit_zero_surface():
    graph = _graph(two_candidates=True)
    record = validate_decision_record_against_candidate_pool(
        _decision(graph), graph["pool"], graph["hypothesis"]
    )
    assert len(record.items) == 2
    assert [item.rank for item in record.items] == [1, 2]

    zero = _graph()
    zero["events"] = zero["events"][:2]
    zero["pool"] = _pool(
        hypothesis=zero["hypothesis"],
        evidence_records=zero["evidence"],
        events=zero["events"],
    )
    zero_pool = _validate_graph(zero)
    empty = validate_decision_record_against_candidate_pool(
        _decision(zero), zero["pool"], zero["hypothesis"]
    )
    assert empty.items == ()
    assert empty.expected_item_count == 0
    assert {item.role for item in zero_pool.comparators} == {"cash", "spy", "qqq", "v1"}


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (lambda row: row["items"].pop(), "decision_surface_incomplete"),
        (lambda row: row["items"][1].update(rank=3), "noncontiguous_decision_ranks"),
        (_swap_decision_item_security_identities, "decision_item_identity_mismatch"),
    ],
)
def test_decision_coverage_rank_and_identity_fail_closed_after_full_reseal(mutator, code):
    graph = _graph(two_candidates=True)
    row = _decision(graph)
    mutator(row)
    row["expected_item_count"] = len(row["items"])
    row = _seal(row, nested_sort=("items", "candidate_entry_id"))
    _assert_code(
        code,
        lambda: validate_decision_record_against_candidate_pool(
            row, graph["pool"], graph["hypothesis"]
        ),
    )


def test_decision_rejects_policy_pool_clock_pit_and_outcome_cross_wires():
    graph = _graph()
    baseline = _decision(
        graph,
        policy_arm="baseline",
        policy_snapshot=graph["hypothesis"]["baseline_policy"],
    )
    validate_decision_record_against_candidate_pool(
        baseline, graph["pool"], graph["hypothesis"]
    )
    wrong = deepcopy(baseline)
    wrong["policy_snapshot"] = graph["hypothesis"]["treatment_policy"]
    wrong = _seal(wrong, nested_sort=("items", "candidate_entry_id"))
    _assert_code(
        "decision_policy_snapshot_mismatch",
        lambda: validate_decision_record_against_candidate_pool(
            wrong, graph["pool"], graph["hypothesis"]
        ),
    )
    wrong_pool = _decision(graph, candidate_pool_hash="0" * 64)
    _assert_code(
        "candidate_pool_hash_mismatch",
        lambda: validate_decision_record_against_candidate_pool(
            wrong_pool, graph["pool"], graph["hypothesis"]
        ),
    )
    too_early = _decision(graph, decided_at="2026-08-20T14:13:30Z", recorded_at="2026-08-20T14:16:00Z")
    _assert_code(
        "decision_before_pool_recorded",
        lambda: validate_decision_record_against_candidate_pool(
            too_early, graph["pool"], graph["hypothesis"]
        ),
    )
    wrong_pit = _decision(graph, pit_tier="not_pit", result_ceiling="invalid")
    _assert_code(
        "decision_evidence_identity_mismatch",
        lambda: validate_decision_record_against_candidate_pool(
            wrong_pit, graph["pool"], graph["hypothesis"]
        ),
    )
    feedback = deepcopy(_decision(graph))
    feedback["settled_outcome_id"] = "future-outcome"
    feedback = _seal(feedback, nested_sort=("items", "candidate_entry_id"))
    _assert_code("unknown_field", lambda: validate_decision_record(feedback))


def test_order_intent_is_never_submitted_and_only_approved_items_can_create_it():
    graph, decision, intent, *_ = _chain(two_candidates=True)
    record = validate_order_intent_against_decision(intent, decision)
    assert record.submitted is False
    assert record.authority == "research_only"
    assert record.trade_enabled is False
    forbidden = deepcopy(intent)
    unselected = next(item for item in decision["items"] if item["signal_action"] == "not_selected")
    forbidden["decision_item_id"] = unselected["decision_item_id"]
    forbidden = _seal(forbidden)
    _assert_code(
        "order_intent_not_approved",
        lambda: validate_order_intent_against_decision(forbidden, decision),
    )
    cross_security = deepcopy(intent)
    for field in ("candidate_entry_id", "security_id", "listing_id", "security_mapping_sha256"):
        cross_security[field] = unselected[field]
    cross_security = _seal(cross_security)
    _assert_code(
        "order_intent_identity_mismatch",
        lambda: validate_order_intent_against_decision(cross_security, decision),
    )

    rejected_items = deepcopy(decision["items"])
    selected = next(item for item in rejected_items if item["signal_action"] == "selected")
    selected.update(
        risk_status="rejected",
        approved_quantity_micros=None,
        approved_notional_minor=None,
        currency=None,
    )
    rejected_decision = _decision(graph, items=rejected_items)
    validate_decision_record_against_candidate_pool(
        rejected_decision, graph["pool"], graph["hypothesis"]
    )
    rejected_intent = deepcopy(intent)
    rejected_intent["decision_hash"] = rejected_decision["semantic_hash"]
    rejected_intent["decision_record_hash"] = rejected_decision["record_hash"]
    rejected_intent["input_snapshot_sha256"] = order_intent_input_snapshot_hash(
        decision_record=rejected_decision,
        decision_item_id=rejected_intent["decision_item_id"],
        side=rejected_intent["side"],
        quantity_micros=rejected_intent["quantity_micros"],
        notional_minor=rejected_intent["notional_minor"],
        currency=rejected_intent["currency"],
        order_type=rejected_intent["order_type"],
        limit_price_minor=rejected_intent["limit_price_minor"],
        stop_price_minor=rejected_intent["stop_price_minor"],
        time_in_force=rejected_intent["time_in_force"],
        not_before=rejected_intent["not_before"],
        expires_at=rejected_intent["expires_at"],
        calendar_session_id=rejected_intent["calendar_session_id"],
        session_clock_id=rejected_intent["session_clock_id"],
        session_clock_hash=rejected_intent["session_clock_hash"],
        session_clock_record_hash=rejected_intent["session_clock_record_hash"],
        execution_rule_id=rejected_intent["execution_rule_id"],
        execution_rule_version=rejected_intent["execution_rule_version"],
        execution_rule_sha256=rejected_intent["execution_rule_sha256"],
        created_at=rejected_intent["created_at"],
    )
    rejected_intent = _seal(rejected_intent)
    _assert_code(
        "order_intent_not_approved",
        lambda: validate_order_intent_against_decision(
            rejected_intent, rejected_decision
        ),
    )

    wrong_side = _intent(decision, side="sell")
    _assert_code(
        "order_intent_side_mismatch",
        lambda: validate_order_intent_against_decision(wrong_side, decision),
    )
    wrong_rule = _intent(decision, execution_rule_sha256="e" * 64)
    _assert_code(
        "execution_rule_mismatch",
        lambda: validate_order_intent_against_decision(wrong_rule, decision),
    )
    next_session = _intent(
        decision,
        calendar_session_id="XNYS-2026-08-21",
        not_before="2026-08-21T13:30:00Z",
        expires_at="2026-08-21T20:00:00Z",
    )
    assert (
        validate_order_intent_against_decision(next_session, decision).calendar_session_id
        == "XNYS-2026-08-21"
    )

    submitted = deepcopy(intent)
    submitted["submitted"] = True
    submitted = _seal(submitted)
    _assert_code("submitted_order_forbidden", lambda: validate_order_intent(submitted))


@pytest.mark.parametrize(
    ("overrides", "against_decision", "code"),
    [
        (
            {"order_type": "market", "limit_price_minor": 10_000},
            False,
            "order_price_fields_mismatch",
        ),
        (
            {"order_type": "limit", "limit_price_minor": None},
            False,
            "order_price_fields_mismatch",
        ),
        (
            {
                "order_type": "stop_limit",
                "limit_price_minor": 10_000,
                "stop_price_minor": None,
            },
            False,
            "order_price_fields_mismatch",
        ),
        (
            {"created_at": "2026-08-20T14:18:30Z"},
            False,
            "invalid_order_intent_chronology",
        ),
        (
            {
                "created_at": "2026-08-20T14:15:00Z",
                "recorded_at": "2026-08-20T14:17:00Z",
                "not_before": "2026-08-20T14:18:00Z",
            },
            True,
            "intent_created_before_decision_recorded",
        ),
        ({"quantity_micros": 1_000_000}, False, "order_size_xor_required"),
        ({"quantity_micros": 1.5}, False, "integer_required"),
    ],
)
def test_order_intent_price_clock_and_integer_contracts(
    overrides, against_decision, code
):
    graph = _graph()
    decision = _decision(graph)

    def validate_case():
        row = _intent(decision, **overrides)
        if against_decision:
            validate_order_intent_against_decision(row, decision)
        else:
            validate_order_intent(row)

    _assert_code(code, validate_case)


def test_settled_outcome_binds_frozen_snapshots_and_synthetic_evidence():
    graph, decision, intent, evidence, outcome, *_ = _chain()
    record = validate_settled_outcome_against_inputs(
        outcome, decision, intent, evidence, [graph["source"]]
    )
    assert isinstance(record, SettledOutcome)
    assert record.fill_snapshot_sha256 == "e" * 64
    assert record.position_snapshot_sha256 == "f" * 64
    assert record.net_pnl_minor == 10_000
    crosswire = deepcopy(outcome)
    crosswire["fill_snapshot_sha256"] = "0" * 64
    crosswire = _seal(crosswire, list_fields=("settlement_evidence_record_ids",))
    _assert_code(
        "input_snapshot_hash_mismatch",
        lambda: validate_settled_outcome_against_inputs(
            crosswire, decision, intent, evidence, [graph["source"]]
        ),
    )
    foreign_mapping = _mapping(
        mapping_id="map-sec-bbb-xnys-settlement-v1",
        security_id="sec-bbb",
        listing_id="listing-bbb-xnys",
        symbol="BBB",
        mic="XNYS",
    )
    foreign_evidence = [
        _measurement_evidence(graph, "7", security_mapping=foreign_mapping)
    ]
    foreign_outcome = _outcome(decision, intent, foreign_evidence)
    _assert_code(
        "settlement_evidence_security_mismatch",
        lambda: validate_settled_outcome_against_inputs(
            foreign_outcome,
            decision,
            intent,
            foreign_evidence,
            [graph["source"]],
        ),
    )
    for row, code in (
        (_outcome(decision, intent, evidence, horizon="two-sessions"), "outcome_horizon_mismatch"),
        (_outcome(decision, intent, evidence, currency="EUR"), "outcome_currency_mismatch"),
        (
            _outcome(decision, intent, evidence, basis_notional_minor=99_999),
            "outcome_basis_notional_mismatch",
        ),
        (
            _outcome(decision, intent, evidence, cost_rule_sha256="0" * 64),
            "cost_rule_mismatch",
        ),
        (
            _outcome(decision, intent, evidence, comparison_rule_sha256="0" * 64),
            "comparison_rule_mismatch",
        ),
    ):
        _assert_code(
            code,
            lambda row=row: validate_settled_outcome_against_inputs(
                row, decision, intent, evidence, [graph["source"]]
            ),
        )


def test_outcome_settled_arithmetic_and_unavailable_row_are_explicit():
    graph, decision, intent, evidence, outcome, *_ = _chain()
    bad_net = deepcopy(outcome)
    bad_net["net_pnl_minor"] += 1
    bad_net = _seal(bad_net, list_fields=("settlement_evidence_record_ids",))
    _assert_code("net_pnl_mismatch", lambda: validate_settled_outcome(bad_net))
    missing_evidence = _outcome(decision, intent, [])
    _assert_code(
        "settled_evidence_required",
        lambda: validate_settled_outcome(missing_evidence),
    )
    unavailable = _outcome(decision, intent, [], status="unavailable")
    record = validate_settled_outcome_against_inputs(
        unavailable, decision, intent, [], [graph["source"]]
    )
    assert record.status == "unavailable"
    assert record.net_pnl_minor is None
    leaked_value = deepcopy(unavailable)
    leaked_value["net_pnl_minor"] = 0
    leaked_value = _seal(leaked_value, list_fields=("settlement_evidence_record_ids",))
    _assert_code("unavailable_values_forbidden", lambda: validate_settled_outcome(leaked_value))


def test_outcome_clocks_and_pit_leakage_propagate_without_decision_feedback():
    graph = _graph()
    decision = _decision(graph)
    intent = _intent(decision)
    leaking = [_measurement_evidence(graph, "8", pit_tier="not_pit", known_future_leakage=True)]
    outcome = _outcome(
        decision,
        intent,
        leaking,
        pit_tier="not_pit",
        result_ceiling="invalid",
        known_future_leakage=True,
    )
    validate_settled_outcome_against_inputs(
        outcome, decision, intent, leaking, [graph["source"]]
    )
    assert decision["input_snapshot_sha256"] == _decision(graph)["input_snapshot_sha256"]
    dropped = deepcopy(outcome)
    dropped["known_future_leakage"] = False
    dropped = _seal(dropped, list_fields=("settlement_evidence_record_ids",))
    _assert_code(
        "outcome_evidence_identity_mismatch",
        lambda: validate_settled_outcome_against_inputs(
            dropped, decision, intent, leaking, [graph["source"]]
        ),
    )
    late = deepcopy(leaking[0])
    late["recorded_at"] = "2026-08-20T15:34:00Z"
    late = _seal(late)
    _assert_code(
        "settlement_evidence_snapshot_mismatch",
        lambda: validate_settled_outcome_against_inputs(
            outcome, decision, intent, [late], [graph["source"]]
        ),
    )
    late_bound = _outcome(decision, intent, [late])
    _assert_code(
        "settlement_evidence_after_settlement",
        lambda: validate_settled_outcome_against_inputs(
            late_bound, decision, intent, [late], [graph["source"]]
        ),
    )

    canonical_graph = _graph(pit_tier="canonical_pit")
    canonical_decision = _decision(canonical_graph)
    capped_decision = validate_decision_record_against_candidate_pool(
        canonical_decision,
        canonical_graph["pool"],
        canonical_graph["hypothesis"],
    )
    assert (capped_decision.pit_tier, capped_decision.result_ceiling) == (
        "research_pit",
        "observed_only",
    )
    forbidden_decision = _decision(
        canonical_graph,
        pit_tier="canonical_pit",
        result_ceiling="gate_eligible",
    )
    _assert_code(
        "decision_context_contract_incomplete",
        lambda: validate_decision_record(forbidden_decision),
    )
    canonical_intent = _intent(canonical_decision)
    canonical_source = _source(
        source_contract_id="source-canonical-measurement-v1",
        maximum_pit_tier="canonical_pit",
        replay_daily_parity_status="pass",
    )
    canonical_evidence = [
        _measurement_evidence(
            canonical_graph,
            "6",
            source=canonical_source,
            pit_tier="canonical_pit",
        )
    ]
    forbidden_canonical = _outcome(
        canonical_decision,
        canonical_intent,
        canonical_evidence,
        pit_tier="canonical_pit",
        result_ceiling="gate_eligible",
    )
    _assert_code(
        "execution_snapshot_contract_incomplete",
        lambda: validate_settled_outcome(forbidden_canonical),
    )
    capped = _outcome(
        canonical_decision,
        canonical_intent,
        canonical_evidence,
        pit_tier="research_pit",
        result_ceiling="observed_only",
    )
    capped_record = validate_settled_outcome_against_inputs(
        capped,
        canonical_decision,
        canonical_intent,
        canonical_evidence,
        [canonical_source],
    )
    assert (capped_record.pit_tier, capped_record.result_ceiling) == (
        "research_pit",
        "observed_only",
    )


def test_outcome_revision_identity_requires_exact_previous_record_reference():
    graph, decision, intent, evidence, first, *_ = _chain()
    second = _outcome(
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
    validate_settled_outcome_against_inputs(
        second,
        decision,
        intent,
        evidence,
        [graph["source"]],
        previous_outcome=first,
    )
    wrong = deepcopy(second)
    wrong["previous_outcome_record_hash"] = "0" * 64
    wrong = _seal(wrong, list_fields=("settlement_evidence_record_ids",))
    _assert_code(
        "previous_outcome_binding_mismatch",
        lambda: validate_settled_outcome_against_inputs(
            wrong,
            decision,
            intent,
            evidence,
            [graph["source"]],
            previous_outcome=first,
        ),
    )
    nonmonotonic = _outcome(
        decision,
        intent,
        evidence,
        outcome_id="outcome-intent-20260820-r2-early",
        revision_number=2,
        previous_outcome_id=first["outcome_id"],
        previous_outcome_record_hash=first["record_hash"],
        settled_at="2026-08-20T15:33:30Z",
        recorded_at="2026-08-20T15:33:45Z",
    )
    _assert_code(
        "nonmonotonic_outcome_revision",
        lambda: validate_settled_outcome_against_inputs(
            nonmonotonic,
            decision,
            intent,
            evidence,
            [graph["source"]],
            previous_outcome=first,
        ),
    )
    reused_id = _outcome(
        decision,
        intent,
        evidence,
        outcome_id=first["outcome_id"],
        revision_number=2,
        previous_outcome_id=first["outcome_id"],
        previous_outcome_record_hash=first["record_hash"],
        settled_at="2026-08-20T15:40:00Z",
        recorded_at="2026-08-20T15:41:00Z",
    )
    _assert_code(
        "previous_outcome_binding_mismatch",
        lambda: validate_settled_outcome_against_inputs(
            reused_id,
            decision,
            intent,
            evidence,
            [graph["source"]],
            previous_outcome=first,
        ),
    )
    regressed = _outcome(
        decision,
        intent,
        [],
        status="unavailable",
        outcome_id="outcome-intent-20260820-r2-unavailable",
        revision_number=2,
        previous_outcome_id=first["outcome_id"],
        previous_outcome_record_hash=first["record_hash"],
        settled_at="2026-08-20T15:40:00Z",
        recorded_at="2026-08-20T15:41:00Z",
    )
    _assert_code(
        "settled_outcome_revision_regression",
        lambda: validate_settled_outcome_against_inputs(
            regressed,
            decision,
            intent,
            [],
            [graph["source"]],
            previous_outcome=first,
        ),
    )


def test_replacement_value_binds_outcome_pool_comparator_and_net_arithmetic():
    graph, _, _, _, outcome, evidence, replacements = _chain()
    row = replacements[0]
    record = validate_replacement_value_against_inputs(
        row, outcome, graph["pool"], evidence, graph["measurement_sources"]
    )
    assert isinstance(record, ReplacementValue)
    assert record.strategy_value_minor == outcome["net_pnl_minor"]
    assert record.basis_notional_minor == outcome["basis_notional_minor"]
    assert record.replacement_value_minor == record.strategy_value_minor - record.comparator_value_minor
    missing_evidence = _replacement(outcome, graph["pool"], [], "cash")
    _assert_code(
        "computed_evidence_required",
        lambda: validate_replacement_value(missing_evidence),
    )
    wrong = deepcopy(row)
    wrong["replacement_value_minor"] += 1
    wrong = _seal(wrong, list_fields=("comparator_evidence_record_ids",))
    _assert_code("replacement_value_mismatch", lambda: validate_replacement_value(wrong))
    wrong_comparator = deepcopy(row)
    wrong_comparator["comparator_reference_id"] = "SPY"
    wrong_comparator = _seal(
        wrong_comparator, list_fields=("comparator_evidence_record_ids",)
    )
    _assert_code(
        "replacement_comparator_binding_mismatch",
        lambda: validate_replacement_value_against_inputs(
            wrong_comparator,
            outcome,
            graph["pool"],
            evidence,
            graph["measurement_sources"],
        ),
    )
    wrong_rule = _replacement(
        outcome,
        graph["pool"],
        [evidence[0]],
        "cash",
        comparison_rule_sha256="0" * 64,
    )
    _assert_code(
        "comparison_rule_mismatch",
        lambda: validate_replacement_value_against_inputs(
            wrong_rule,
            outcome,
            graph["pool"],
            evidence,
            graph["measurement_sources"],
        ),
    )


def test_replacement_unavailable_row_preserves_panel_identity():
    graph, _, _, _, outcome, evidence, _ = _chain()
    row = _replacement(
        outcome, graph["pool"], [], "cash", status="unavailable"
    )
    record = validate_replacement_value_against_inputs(
        row,
        outcome,
        graph["pool"],
        [],
        graph["measurement_sources"],
    )
    assert record.status == "unavailable"
    assert record.replacement_value_minor is None


def test_replacement_panel_requires_exact_unique_cash_spy_qqq_v1_coverage():
    graph, _, _, _, outcome, evidence, rows = _chain()
    panel = validate_replacement_value_panel(
        rows,
        outcome,
        graph["pool"],
        evidence,
        graph["measurement_sources"],
    )
    assert [item.comparator_role for item in panel] == ["cash", "qqq", "spy", "v1"]
    _assert_code(
        "replacement_panel_incomplete",
        lambda: validate_replacement_value_panel(
            rows[:-1],
            outcome,
            graph["pool"],
            evidence,
            graph["measurement_sources"],
        ),
    )
    duplicate = [*rows[:-1], deepcopy(rows[0])]
    duplicate[-1]["replacement_value_id"] = "replacement-cash-duplicate"
    duplicate[-1] = _seal(duplicate[-1], list_fields=("comparator_evidence_record_ids",))
    _assert_code(
        "replacement_panel_incomplete",
        lambda: validate_replacement_value_panel(
            duplicate,
            outcome,
            graph["pool"],
            evidence,
            graph["measurement_sources"],
        ),
    )


def test_replacement_full_reseal_cross_wires_and_late_evidence_fail_closed():
    graph, _, _, _, outcome, evidence, rows = _chain()
    wrong = deepcopy(rows[1])
    wrong["candidate_pool_hash"] = "0" * 64
    wrong = _seal(wrong, list_fields=("comparator_evidence_record_ids",))
    _assert_code(
        "replacement_pool_binding_mismatch",
        lambda: validate_replacement_value_against_inputs(
            wrong,
            outcome,
            graph["pool"],
            evidence,
            graph["measurement_sources"],
        ),
    )
    late = deepcopy(evidence[1])
    late["recorded_at"] = "2026-08-20T15:40:00Z"
    late = _seal(late)
    _assert_code(
        "comparator_evidence_snapshot_mismatch",
        lambda: validate_replacement_value_against_inputs(
            rows[1],
            outcome,
            graph["pool"],
            [late],
            graph["measurement_sources"],
        ),
    )
    late_bound = _replacement(outcome, graph["pool"], [late], "spy")
    _assert_code(
        "comparator_evidence_after_settlement",
        lambda: validate_replacement_value_against_inputs(
            late_bound,
            outcome,
            graph["pool"],
            [late],
            graph["measurement_sources"],
        ),
    )
    leaking = deepcopy(evidence[1])
    leaking["pit_tier"] = "not_pit"
    leaking["known_future_leakage"] = True
    leaking = _seal(leaking)
    leaking_row = _replacement(
        outcome,
        graph["pool"],
        [leaking],
        "spy",
        pit_tier="not_pit",
        result_ceiling="invalid",
        known_future_leakage=True,
    )
    validate_replacement_value_against_inputs(
        leaking_row,
        outcome,
        graph["pool"],
        [leaking],
        graph["measurement_sources"],
    )
    dropped = deepcopy(leaking_row)
    dropped["known_future_leakage"] = False
    dropped = _seal(dropped, list_fields=("comparator_evidence_record_ids",))
    _assert_code(
        "replacement_evidence_identity_mismatch",
        lambda: validate_replacement_value_against_inputs(
            dropped,
            outcome,
            graph["pool"],
            [leaking],
            graph["measurement_sources"],
        ),
    )
    spy_with_qqq_evidence = _replacement(
        outcome, graph["pool"], [evidence[2]], "spy"
    )
    _assert_code(
        "comparator_evidence_reference_mismatch",
        lambda: validate_replacement_value_against_inputs(
            spy_with_qqq_evidence,
            outcome,
            graph["pool"],
            [evidence[2]],
            graph["measurement_sources"],
        ),
    )
    spy = next(
        item for item in graph["pool"]["comparators"] if item["role"] == "spy"
    )
    disguised_qqq = deepcopy(evidence[2])
    disguised_qqq["decision_content"]["comparator_reference_id"] = spy[
        "reference_id"
    ]
    disguised_qqq["decision_content"][
        "comparator_reference_snapshot_sha256"
    ] = spy["reference_snapshot_sha256"]
    disguised_qqq["decision_content_sha256"] = canonical_hash(
        disguised_qqq["decision_content"]
    )
    disguised_qqq = _seal(disguised_qqq)
    spy_with_wrong_mapping = _replacement(
        outcome, graph["pool"], [disguised_qqq], "spy"
    )
    _assert_code(
        "comparator_evidence_security_mismatch",
        lambda: validate_replacement_value_against_inputs(
            spy_with_wrong_mapping,
            outcome,
            graph["pool"],
            [disguised_qqq],
            graph["measurement_sources"],
        ),
    )
    cash = next(
        item for item in graph["pool"]["comparators"] if item["role"] == "cash"
    )
    cash_instrument = deepcopy(evidence[1])
    cash_instrument["decision_content"]["comparator_reference_id"] = cash[
        "reference_id"
    ]
    cash_instrument["decision_content"][
        "comparator_reference_snapshot_sha256"
    ] = cash["reference_snapshot_sha256"]
    cash_instrument["decision_content_sha256"] = canonical_hash(
        cash_instrument["decision_content"]
    )
    cash_instrument = _seal(cash_instrument)
    cash_with_instrument_evidence = _replacement(
        outcome, graph["pool"], [cash_instrument], "cash"
    )
    _assert_code(
        "comparator_instrument_evidence_forbidden",
        lambda: validate_replacement_value_against_inputs(
            cash_with_instrument_evidence,
            outcome,
            graph["pool"],
            [cash_instrument],
            graph["measurement_sources"],
        ),
    )


def test_replacement_revision_references_immediately_previous_comparator_row():
    graph, decision, intent, settlement_evidence, first_outcome, comparator_evidence, first_rows = _chain()
    second_outcome = _outcome(
        decision,
        intent,
        settlement_evidence,
        outcome_id="outcome-intent-20260820-r2",
        revision_number=2,
        previous_outcome_id=first_outcome["outcome_id"],
        previous_outcome_record_hash=first_outcome["record_hash"],
        settled_at="2026-08-20T15:40:00Z",
        recorded_at="2026-08-20T15:41:00Z",
    )
    validate_settled_outcome_against_inputs(
        second_outcome,
        decision,
        intent,
        settlement_evidence,
        [graph["source"]],
        previous_outcome=first_outcome,
    )
    second_rows = [
        _replacement(
            second_outcome,
            graph["pool"],
            [evidence],
            role,
            previous_replacement_value_id=previous["replacement_value_id"],
            previous_replacement_value_record_hash=previous["record_hash"],
            settled_at="2026-08-20T15:42:00Z",
            recorded_at="2026-08-20T15:43:00Z",
        )
        for evidence, role, previous in zip(
            comparator_evidence,
            ("cash", "spy", "qqq", "v1"),
            first_rows,
        )
    ]
    validate_replacement_value_panel(
        second_rows,
        second_outcome,
        graph["pool"],
        comparator_evidence,
        graph["measurement_sources"],
        previous_replacement_values=first_rows,
    )
    _assert_code(
        "previous_replacement_panel_incomplete",
        lambda: validate_replacement_value_panel(
            second_rows,
            second_outcome,
            graph["pool"],
            comparator_evidence,
            graph["measurement_sources"],
            previous_replacement_values=first_rows[:-1],
        ),
    )
    previous = first_rows[0]
    second = second_rows[0]
    wrong = deepcopy(second)
    wrong["previous_replacement_value_record_hash"] = "0" * 64
    wrong = _seal(wrong, list_fields=("comparator_evidence_record_ids",))
    _assert_code(
        "previous_replacement_binding_mismatch",
        lambda: validate_replacement_value_against_inputs(
            wrong,
            second_outcome,
            graph["pool"],
            comparator_evidence,
            graph["measurement_sources"],
            previous_replacement_value=previous,
        ),
    )
    reused_id = deepcopy(second)
    reused_id["replacement_value_id"] = previous["replacement_value_id"]
    reused_id = _seal(
        reused_id, list_fields=("comparator_evidence_record_ids",)
    )
    _assert_code(
        "previous_replacement_binding_mismatch",
        lambda: validate_replacement_value_against_inputs(
            reused_id,
            second_outcome,
            graph["pool"],
            comparator_evidence,
            graph["measurement_sources"],
            previous_replacement_value=previous,
        ),
    )
    regressed = _replacement(
        second_outcome,
        graph["pool"],
        [],
        "cash",
        status="unavailable",
        previous_replacement_value_id=previous["replacement_value_id"],
        previous_replacement_value_record_hash=previous["record_hash"],
        settled_at="2026-08-20T15:42:00Z",
        recorded_at="2026-08-20T15:43:00Z",
    )
    _assert_code(
        "computed_replacement_revision_regression",
        lambda: validate_replacement_value_against_inputs(
            regressed,
            second_outcome,
            graph["pool"],
            [],
            graph["measurement_sources"],
            previous_replacement_value=previous,
        ),
    )


def test_dataclass_inputs_are_revalidated_instead_of_trusted():
    graph, decision, intent, evidence, outcome, comparator_evidence, rows = _chain()
    decision_obj = validate_decision_record(decision)
    intent_obj = validate_order_intent(intent)
    outcome_obj = validate_settled_outcome(outcome)
    replacement_obj = validate_replacement_value(rows[0])
    for validator, record in (
        (validate_decision_record, decision_obj),
        (validate_order_intent, intent_obj),
        (validate_settled_outcome, outcome_obj),
        (validate_replacement_value, replacement_obj),
    ):
        _assert_code(
            "trade_enabled_forbidden",
            lambda validator=validator, record=record: validator(
                replace(record, trade_enabled=True)
            ),
        )
    _assert_code(
        "semantic_hash_mismatch",
        lambda: validate_decision_record(replace(decision_obj, candidate_pool_id="tampered")),
    )
    _assert_code(
        "submitted_order_forbidden",
        lambda: validate_order_intent(replace(intent_obj, submitted=True)),
    )
    _assert_code(
        "net_pnl_mismatch",
        lambda: validate_settled_outcome(replace(outcome_obj, net_pnl_minor=9_999)),
    )
    _assert_code(
        "replacement_value_mismatch",
        lambda: validate_replacement_value(
            replace(replacement_obj, replacement_value_minor=9_999)
        ),
    )
    validate_settled_outcome_against_inputs(
        outcome_obj, decision_obj, intent_obj, evidence, [graph["source"]]
    )
    validate_replacement_value_panel(
        rows,
        outcome_obj,
        graph["pool"],
        comparator_evidence,
        graph["measurement_sources"],
    )
