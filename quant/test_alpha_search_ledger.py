from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

import quant.alpha_search_ledger as ledger_module
from quant.alpha_search_contract import (
    build_hypothesis_candidate,
    build_selection_panel,
    canonical_hash,
)
from quant.alpha_search_ledger import (
    AlphaSearchLedgerConflictError,
    AlphaSearchLedgerValidationError,
    append_alpha_search_event,
    append_discovery_batch,
    append_discovery_event,
    load_alpha_search_events,
    make_alpha_search_event,
    validate_alpha_search_event,
)


NOW = "2026-07-21T12:00:00Z"


def _candidate_raw(candidate_id="candidate-a", *, suffix="a"):
    return {
        "candidate_id": candidate_id,
        "queue": "explore",
        "hypothesis": f"Independent facts imply a repricing gap {suffix}.",
        "baseline": "Rank the frozen universe without the event-state admission.",
        "treatment": f"Admit event-state candidate under mapping {suffix}.",
        "horizon": "H5-H20",
        "replacement_comparison": "Cash, SPY, QQQ, and displaced core candidate.",
        "decision_surface": "candidate_pool",
        "mechanism_family": f"policy_probability_repricing_{suffix}",
        "fingerprint": {
            "data_source": "polymarket",
            "component_sources": ["polymarket", "sec"],
            "expectation_proxy": "direct_implied_probability",
            "economic_mechanism": f"policy_probability_repricing_{suffix}",
            "decision_surface": "candidate_pool",
            "payoff_shape": "long_convex_event_drift",
            "horizon": "H5-H20",
            "execution_dependency": "liquid_cash_equity",
            "portfolio_role": "orthogonal_event_sleeve",
        },
        "surface_ids": ["prediction_market_event_observer", "sec_event_stream"],
        "data_source": "polymarket",
        "component_sources": ["polymarket", "sec"],
        "expectation_gap": {
            "market_prior": {
                "observable": True,
                "proxy_type": "direct_implied_probability",
                "source": "polymarket",
                "known_at": "2026-07-20T12:30:00Z",
                "value": 0.38,
            },
            "independent_evidence": [
                {
                    "evidence_id": f"sec-{suffix}",
                    "source": "SEC",
                    "known_at": "2026-07-20T15:05:00Z",
                    "state": "condition_satisfied",
                }
            ],
            "gap_definition": "calibrated posterior minus observable market prior",
            "transmission": {
                "affected_tickers": ["AAA"],
                "expected_direction": "long",
                "catalyst": "formal event resolution",
                "half_life": "H5-H20",
            },
        },
        "why_not_arbitraged": "Issuer mapping and event semantics are costly.",
        "falsifier": "No repricing after confirmed evidence within H20.",
        "evidence_grade": "observer",
        "next_machine_action": "Keep the observer default-off.",
        "execution": {
            "instrument": "cash_equity",
            "liquidity_dependency": "minimum decision-time ADV",
            "costs_and_carry": "explicit fixed estimate",
            "borrow_dependency": "none",
            "capacity_constraint": "fixed research cap",
            "timing_constraint": "next session open",
            "trade_enabled": False,
            "orders_enabled": False,
            "live_ready": False,
        },
        "portfolio_role": "orthogonal_event_sleeve",
        "production_impact": {"trade_enabled": False, "orders_changed": False},
    }


def _candidate(candidate_id="candidate-a", *, suffix="a"):
    return build_hypothesis_candidate(
        _candidate_raw(candidate_id, suffix=suffix)
    ).to_dict()


def _candidate_event(
    candidate_id="candidate-a",
    *,
    suffix="a",
    selection_scope_id="scope-ledger-standalone-a",
    event_id=None,
    recorded_at=NOW,
):
    return make_alpha_search_event(
        record_type="candidate_snapshot",
        payload=_candidate(candidate_id, suffix=suffix),
        selection_scope_id=selection_scope_id,
        event_id=event_id,
        recorded_at=recorded_at,
    )


def _scope_manifest():
    manifest = {
        "schema_version": 1,
        "manifest_version": "alpha_search_scope_manifest_v1",
        "scope_name": "ledger-test-scope",
        "preregistered_at": "2026-07-20T00:00:00Z",
        "data_cutoff": "2026-07-20T12:00:00Z",
        "freeze_at": "2026-07-21T00:00:00Z",
        "generator_version": "ledger-test-generator-v1",
        "candidate_generation_config": {"fixture": "single-exploration-candidate"},
        "prior_fingerprint_snapshot_hash": canonical_hash([]),
        "prior_fingerprint_count": 0,
        "allowed_surface_ids": [
            "prediction_market_event_observer",
            "sec_event_stream",
        ],
        "surface_registry_hash": "c" * 64,
        "selector_version": "ledger-test-selector-v1",
        "score_version": "ledger-test-score-v1",
        "queue_budgets": {
            "exploration": 1,
            "adjacent": 0,
            "exploitation": 0,
        },
        "expected_candidate_count": 1,
        "selection_limit": 1,
        "batch_policy_bundle_id": None,
        "outcome_blind": True,
        "trade_enabled": False,
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    return manifest


def _panel(candidate_id="candidate-a", *, suffix="a"):
    return build_selection_panel(
        [_candidate(candidate_id, suffix=suffix)],
        scope_manifest=_scope_manifest(),
    ).to_dict()


def _scope_specs(panel, *, recorded_at=NOW):
    specs = [
        {
            "record_type": "candidate_snapshot",
            "payload": candidate,
            "recorded_at": recorded_at,
        }
        for candidate in panel["candidate_snapshots"]
    ]
    specs.extend(
        {
            "record_type": "preflight_decision",
            "payload": preflight,
            "recorded_at": recorded_at,
        }
        for preflight in panel["preflight_decisions"].values()
    )
    specs.append(
        {
            "record_type": "panel_selection",
            "payload": panel,
            "recorded_at": recorded_at,
        }
    )
    return specs


def test_make_dispatches_candidate_contract_and_derives_natural_identity():
    payload = _candidate()
    event = make_alpha_search_event(
        record_type="candidate_snapshot",
        payload=payload,
        selection_scope_id="scope-direct-a",
        recorded_at=NOW,
    )
    validated = validate_alpha_search_event(event)

    assert validated == event
    assert validated is not event
    assert event["identity"] == {
        "selection_scope_id": "scope-direct-a",
        "candidate_id": payload["candidate_id"],
    }
    assert payload["candidate_id"].startswith("cand-")
    assert event["payload"]["schema_version"] == 1
    assert len(event["identity_hash"]) == 64


def test_content_hash_may_not_be_smuggled_into_natural_identity():
    payload = _candidate()
    with pytest.raises(AlphaSearchLedgerValidationError, match="natural key"):
        make_alpha_search_event(
            record_type="candidate_snapshot",
            payload=payload,
            identity={
                "selection_scope_id": "scope-direct-a",
                "candidate_id": payload["candidate_id"],
                "candidate_hash": "a" * 64,
            },
        )


def test_semantic_candidate_alias_cannot_bypass_durable_identity():
    aliased = _candidate()
    aliased["candidate_id"] = "cand-arbitrary-alias"

    with pytest.raises(AlphaSearchLedgerValidationError, match="candidate_id_mismatch"):
        make_alpha_search_event(
            record_type="candidate_snapshot",
            payload=aliased,
            selection_scope_id="scope-direct-a",
        )


def test_preflight_and_panel_identities_reject_content_hash_fields():
    panel = _panel()
    preflight = next(iter(panel["preflight_decisions"].values()))

    with pytest.raises(AlphaSearchLedgerValidationError, match="natural key"):
        make_alpha_search_event(
            record_type="preflight_decision",
            payload=preflight,
            identity={
                "selection_scope_id": panel["selection_scope_id"],
                "candidate_id": preflight["candidate_id"],
                "preflight_version": preflight["preflight_version"],
                "preflight_hash": preflight["preflight_hash"],
            },
        )
    with pytest.raises(AlphaSearchLedgerValidationError, match="natural key"):
        make_alpha_search_event(
            record_type="panel_selection",
            payload=panel,
            identity={
                "selection_scope_id": panel["selection_scope_id"],
                "panel_hash": panel["panel_hash"],
            },
        )


def test_record_type_payloads_are_strictly_dispatched():
    panel = _panel()
    preflight = next(iter(panel["preflight_decisions"].values()))

    with pytest.raises(AlphaSearchLedgerValidationError, match="strict contract"):
        make_alpha_search_event(
            record_type="candidate_snapshot",
            payload=preflight,
        )


def test_full_scope_batch_uses_one_atomic_replace_and_is_idempotent(
    tmp_path, monkeypatch
):
    path = tmp_path / "events.jsonl"
    panel = _panel()
    real_atomic_write = ledger_module.atomic_write_text
    calls = []

    def counted_write(text, filepath):
        calls.append((text, filepath))
        real_atomic_write(text, filepath)

    monkeypatch.setattr(ledger_module, "atomic_write_text", counted_write)
    first = append_discovery_batch(path, _scope_specs(panel))
    retry = append_discovery_batch(
        path,
        _scope_specs(panel, recorded_at="2026-07-21T12:05:00Z"),
    )

    assert first["status"] == "appended"
    assert first["rows_written"] == 3
    assert retry["status"] == "duplicate"
    assert retry["rows_written"] == 0
    assert len(calls) == 1
    rows = load_alpha_search_events(path)
    assert [row["record_type"] for row in rows] == [
        "candidate_snapshot",
        "preflight_decision",
        "panel_selection",
    ]
    candidate_id = panel["candidate_ids"][0]
    assert rows[0]["identity"] == {
        "selection_scope_id": panel["selection_scope_id"],
        "candidate_id": candidate_id,
    }
    assert rows[1]["identity"] == {
        "selection_scope_id": panel["selection_scope_id"],
        "candidate_id": candidate_id,
        "preflight_version": rows[1]["payload"]["preflight_version"],
    }
    assert rows[2]["identity"] == {
        "selection_scope_id": panel["selection_scope_id"]
    }


@pytest.mark.parametrize("missing_type", ["candidate_snapshot", "preflight_decision"])
def test_panel_batch_requires_complete_candidate_and_preflight_sets(
    tmp_path, missing_type
):
    path = tmp_path / "events.jsonl"
    specs = [
        spec for spec in _scope_specs(_panel()) if spec["record_type"] != missing_type
    ]

    with pytest.raises(AlphaSearchLedgerValidationError, match="incomplete"):
        append_discovery_batch(path, specs)

    assert not path.exists()


def test_panel_batch_rejects_candidate_snapshot_bound_to_another_scope(tmp_path):
    path = tmp_path / "events.jsonl"
    specs = _scope_specs(_panel())
    specs[0]["selection_scope_id"] = "scope-wrong"

    with pytest.raises(
        AlphaSearchLedgerValidationError,
        match="candidate snapshot scope mismatch",
    ):
        append_discovery_batch(path, specs)

    assert not path.exists()


def test_append_same_candidate_identity_and_content_is_idempotent(tmp_path):
    path = tmp_path / "events.jsonl"
    first = append_alpha_search_event(path, _candidate_event())
    retry = append_alpha_search_event(
        path,
        _candidate_event(event_id="caller-retry-id", recorded_at="2026-07-21T12:05:00Z"),
    )

    assert first["status"] == "appended"
    assert retry["status"] == "duplicate"
    assert retry["event_id"] == first["event_id"]
    assert len(load_alpha_search_events(path)) == 1


def test_same_candidate_natural_key_with_changed_content_is_conflict(tmp_path):
    path = tmp_path / "events.jsonl"
    payload = _candidate()
    append_alpha_search_event(
        path,
        make_alpha_search_event(
            record_type="candidate_snapshot",
            payload=payload,
            selection_scope_id="scope-refresh-a",
            recorded_at=NOW,
        ),
    )
    changed = deepcopy(payload)
    # Authorship metadata is deliberately excluded from the semantic cand- ID
    # but remains immutable durable content.
    changed["created_at"] = "2026-07-21T00:00:00Z"

    with pytest.raises(AlphaSearchLedgerConflictError, match="identity"):
        append_alpha_search_event(
            path,
            make_alpha_search_event(
                record_type="candidate_snapshot",
                payload=changed,
                selection_scope_id="scope-refresh-a",
                recorded_at=NOW,
            ),
        )

    assert len(load_alpha_search_events(path)) == 1


def test_same_semantic_candidate_may_be_snapshotted_in_distinct_scopes(tmp_path):
    path = tmp_path / "events.jsonl"
    original = _candidate()
    refreshed = deepcopy(original)
    # Authorship/readiness metadata is deliberately excluded from the cand-
    # semantic ID.  A refreshed discovery scope must still be able to freeze
    # its own immutable snapshot instead of colliding with the prior scope.
    refreshed["created_at"] = "2026-07-21T00:00:00Z"

    append_alpha_search_event(
        path,
        make_alpha_search_event(
            record_type="candidate_snapshot",
            payload=original,
            selection_scope_id="scope-refresh-a",
            recorded_at=NOW,
        ),
    )
    append_alpha_search_event(
        path,
        make_alpha_search_event(
            record_type="candidate_snapshot",
            payload=refreshed,
            selection_scope_id="scope-refresh-b",
            recorded_at=NOW,
        ),
    )

    rows = load_alpha_search_events(path)
    assert len(rows) == 2
    assert rows[0]["payload"]["candidate_id"] == rows[1]["payload"]["candidate_id"]
    assert {row["identity"]["selection_scope_id"] for row in rows} == {
        "scope-refresh-a",
        "scope-refresh-b",
    }


def test_standalone_candidate_without_scope_fails_closed():
    with pytest.raises(AlphaSearchLedgerValidationError, match="selection_scope_id"):
        make_alpha_search_event(
            record_type="candidate_snapshot",
            payload=_candidate(),
        )


def test_same_event_id_with_different_natural_identity_is_conflict(tmp_path):
    path = tmp_path / "events.jsonl"
    append_alpha_search_event(path, _candidate_event(event_id="fixed-event"))

    with pytest.raises(AlphaSearchLedgerConflictError, match="event_id"):
        append_alpha_search_event(
            path,
            _candidate_event(
                candidate_id="candidate-b", suffix="b", event_id="fixed-event"
            ),
        )


def test_same_preflight_natural_key_with_changed_content_is_conflict(tmp_path):
    path = tmp_path / "events.jsonl"
    panel = _panel()
    append_discovery_batch(path, _scope_specs(panel))
    changed = deepcopy(next(iter(panel["preflight_decisions"].values())))
    # evaluated_at is outside the natural key; recomputing the contract hash
    # therefore produces a valid but conflicting same-key payload.
    changed["evaluated_at"] = "1970-01-02T00:00:00Z"
    changed["preflight_hash"] = canonical_hash(
        {key: value for key, value in changed.items() if key != "preflight_hash"}
    )

    with pytest.raises(AlphaSearchLedgerConflictError, match="identity"):
        append_discovery_event(
            path,
            record_type="preflight_decision",
            payload=changed,
            recorded_at=NOW,
        )


def test_same_panel_scope_with_changed_content_aborts_whole_batch(tmp_path):
    path = tmp_path / "events.jsonl"
    panel = _panel()
    append_discovery_batch(path, _scope_specs(panel))
    before = path.read_text(encoding="utf-8")
    changed = deepcopy(panel)
    # Explanatory selection text is outside scope identity; recomputing
    # panel_hash produces a valid document whose natural key still conflicts.
    changed["selection_reason"] = "A different frozen explanation for no selection."
    changed["panel_hash"] = canonical_hash(
        {key: value for key, value in changed.items() if key != "panel_hash"}
    )

    with pytest.raises(AlphaSearchLedgerConflictError, match="identity"):
        append_discovery_batch(path, _scope_specs(changed))

    assert path.read_text(encoding="utf-8") == before


def test_bad_existing_jsonl_fails_closed_and_is_not_rewritten(tmp_path):
    path = tmp_path / "events.jsonl"
    corrupt = '{"schema_version":1\n'
    path.write_text(corrupt, encoding="utf-8")

    with pytest.raises(AlphaSearchLedgerValidationError, match="invalid JSON"):
        append_alpha_search_event(path, _candidate_event())

    assert path.read_text(encoding="utf-8") == corrupt


def test_existing_hash_tampering_fails_closed(tmp_path):
    path = tmp_path / "events.jsonl"
    event = _candidate_event()
    event["payload"]["hypothesis"] = "Tampered after hashing."
    path.write_text(ledger_module._canonical_json(event) + "\n", encoding="utf-8")

    with pytest.raises(
        AlphaSearchLedgerValidationError,
        match="candidate_id_mismatch|semantic_hash mismatch",
    ):
        load_alpha_search_events(path)


@pytest.mark.parametrize(
    "record_type",
    ["outcome_link", "backtest_result", "candidate_outcome", ""],
)
def test_only_three_discovery_record_types_are_allowed(record_type):
    with pytest.raises(AlphaSearchLedgerValidationError, match="record_type"):
        make_alpha_search_event(
            record_type=record_type,
            payload=_candidate(),
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("realized_return", 0.1),
        ("sharpe_daily", 2.0),
        ("backtest_results", {"ev": 4.0}),
        ("outcome", "winner"),
        ("spy_forward_return", 0.2),
    ],
)
def test_realized_outcome_and_backtest_fields_are_rejected(field, value):
    payload = _candidate()
    payload[field] = value

    with pytest.raises(AlphaSearchLedgerValidationError, match="forbidden"):
        make_alpha_search_event(record_type="candidate_snapshot", payload=payload)


def test_outcome_blind_contract_fields_remain_legal(tmp_path):
    path = tmp_path / "events.jsonl"
    panel = _panel()

    append_discovery_batch(path, _scope_specs(panel))

    rows = load_alpha_search_events(path)
    assert rows[1]["payload"]["outcome_blind"] is True
    assert rows[2]["payload"]["outcome_blind"] is True


def test_atomic_write_failure_preserves_old_ledger_and_releases_lock(
    tmp_path, monkeypatch
):
    path = tmp_path / "events.jsonl"
    append_alpha_search_event(path, _candidate_event())
    original = path.read_text(encoding="utf-8")

    def fail_write(text, filepath):
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(ledger_module, "atomic_write_text", fail_write)
    with pytest.raises(OSError, match="synthetic"):
        append_alpha_search_event(
            path, _candidate_event(candidate_id="candidate-b", suffix="b")
        )

    assert path.read_text(encoding="utf-8") == original
    assert not path.with_name(path.name + ".lock").exists()


def test_full_scope_atomic_failure_leaves_no_partial_rows(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"

    def fail_write(text, filepath):
        raise OSError("synthetic batch replace failure")

    monkeypatch.setattr(ledger_module, "atomic_write_text", fail_write)
    with pytest.raises(OSError, match="batch replace"):
        append_discovery_batch(path, _scope_specs(_panel()))

    assert not path.exists()
    assert not path.with_name(path.name + ".lock").exists()


def test_nonfinite_lock_timeout_is_rejected_without_creating_a_lock(tmp_path):
    path = tmp_path / "events.jsonl"

    with pytest.raises(ledger_module.AlphaSearchLedgerLockError, match="non-negative"):
        append_alpha_search_event(
            path,
            _candidate_event(),
            lock_timeout_seconds=float("nan"),
        )

    assert not path.exists()
    assert not path.with_name(path.name + ".lock").exists()


def test_concurrent_unique_candidate_appends_do_not_drop_suffixes(tmp_path):
    path = tmp_path / "events.jsonl"

    def append_one(index):
        return append_discovery_event(
            path,
            record_type="candidate_snapshot",
            payload=_candidate(f"candidate-{index}", suffix=str(index)),
            selection_scope_id=f"scope-concurrency-{index}",
            recorded_at=NOW,
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(append_one, range(12)))

    assert all(item["rows_written"] == 1 for item in results)
    events = load_alpha_search_events(path)
    assert len(events) == 12
    assert {event["record_type"] for event in events} == {"candidate_snapshot"}
