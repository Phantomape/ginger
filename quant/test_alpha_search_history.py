from __future__ import annotations

import json
from pathlib import Path

import pytest

from quant.alpha_search_history import (
    HistoricalPriorError,
    build_historical_prior_snapshot,
    candidate_legacy_fingerprints,
    legacy_near_neighbors,
    validate_repository_historical_snapshot,
    validate_historical_prior_snapshot,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _family(experiment_id: str = "exp-20260605-029") -> dict:
    return {
        "family_key": "estimate_revision_persistence_underreaction_candidate_pool",
        "fingerprint": {
            "data_source": "revision_expectation",
            "field_tags": [
                "estimate", "persistence", "persistent", "positive", "revision", "underreaction"
            ],
            "gate_shape": "candidate_pool_top1_10d",
        },
        "representative_exps": [experiment_id],
        "status": "single_attempt",
        "reopen_condition": None,
    }


def _muted_candidate() -> dict:
    return {
        "title": "Muted price response after a consensus revision",
        "hypothesis": (
            "A timestamp-safe analyst estimate revision whose contemporaneous price response "
            "is unusually muted identifies underreaction over H5-H20."
        ),
        "fingerprint": {
            "data_source": "ohlcv_warehouse",
            "component_sources": ["analyst_estimate_revision", "ohlcv_warehouse"],
            "expectation_proxy": "price_revealed",
            "economic_mechanism": "muted_price_response_to_consensus_revision",
            "decision_surface": "candidate_pool",
            "payoff_shape": "post_revision_drift",
            "horizon": "H5-H20",
            "execution_dependency": "liquid_cash_equity_next_session",
            "portfolio_role": "expectation_underreaction_sleeve",
        },
    }


def test_snapshot_is_time_anchored_sorted_and_hash_stable(tmp_path: Path) -> None:
    source = tmp_path / "frozen.jsonl"
    _write_jsonl(source, [_family("exp-20260606-001"), _family()])
    first = build_historical_prior_snapshot(
        source, history_cutoff="2026-06-07T00:00:00Z", isolated_fixture=True
    )
    second = build_historical_prior_snapshot(
        source, history_cutoff="2026-06-07T00:00:00Z", isolated_fixture=True
    )
    assert first == second
    assert first["record_count"] == 2
    assert first["records"] == sorted(
        first["records"], key=lambda row: (row["record_id"], row["known_at"])
    )
    assert validate_historical_prior_snapshot(first) == first


def test_snapshot_excludes_rows_not_known_by_cutoff(tmp_path: Path) -> None:
    source = tmp_path / "frozen.jsonl"
    _write_jsonl(source, [_family("exp-20260605-029")])
    snapshot = build_historical_prior_snapshot(
        source, history_cutoff="2026-06-05T12:00:00Z", isolated_fixture=True
    )
    assert snapshot["record_count"] == 0
    assert validate_historical_prior_snapshot(snapshot) == snapshot


def test_component_alias_finds_legacy_revision_neighbor(tmp_path: Path) -> None:
    source = tmp_path / "frozen.jsonl"
    _write_jsonl(source, [_family()])
    snapshot = build_historical_prior_snapshot(
        source, history_cutoff="2026-06-06T00:00:00Z", isolated_fixture=True
    )
    projected = candidate_legacy_fingerprints(_muted_candidate())
    assert "revision_expectation" in {row["data_source"] for row in projected}
    hits = legacy_near_neighbors(_muted_candidate(), snapshot["records"])
    assert hits
    assert hits[0]["representative_exps"] == ["exp-20260605-029"]


def test_snapshot_hash_tampering_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "frozen.jsonl"
    _write_jsonl(source, [_family()])
    snapshot = build_historical_prior_snapshot(
        source, history_cutoff="2026-06-06T00:00:00Z", isolated_fixture=True
    )
    snapshot["records"][0]["family_key"] = "forged"
    with pytest.raises(HistoricalPriorError, match="record identity mismatch"):
        validate_historical_prior_snapshot(snapshot)


def test_optional_discovery_ledger_is_source_anchored(tmp_path: Path) -> None:
    source = tmp_path / "frozen.jsonl"
    ledger = tmp_path / "discovery.jsonl"
    _write_jsonl(source, [_family()])
    candidate = _muted_candidate()
    candidate["candidate_id"] = "cand-muted"
    candidate["created_at"] = "2026-06-05T12:00:00Z"
    _write_jsonl(
        ledger,
        [
            {
                "record_type": "candidate_snapshot",
                "recorded_at": "2026-06-05T12:01:00Z",
                "payload": candidate,
            }
        ],
    )
    snapshot = build_historical_prior_snapshot(
        source,
        history_cutoff="2026-06-06T00:00:00Z",
        discovery_ledgers=[ledger],
        isolated_fixture=True,
    )
    assert {anchor["kind"] for anchor in snapshot["source_anchors"]} == {
        "isolated_frozen_families_asof_projection",
        "discovery_ledger_asof_projection",
    }
    assert any(record["origin"] == "discovery_candidate" for record in snapshot["records"])


def test_canonical_snapshot_is_stable_when_future_rows_are_appended(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    frozen = repo / "docs" / "frozen_families.jsonl"
    logs = repo / "experiments" / "logs"
    logs.mkdir(parents=True)
    frozen.parent.mkdir(parents=True)
    frozen.write_text("{}\n", encoding="utf-8")
    _write_jsonl(
        logs / "exp-20260605-029.json",
        [
            {
                "experiment_id": "exp-20260605-029",
                "timestamp": "2026-06-05T18:00:00Z",
                "trial_family": "estimate_revision_persistence_underreaction_candidate_pool",
                "changed_variable": "persistent positive estimate revision underreaction",
                "status": "rejected",
                "next_retry_requires": ["new forward evidence"],
            }
        ],
    )
    first = build_historical_prior_snapshot(
        frozen,
        history_cutoff="2026-06-06T00:00:00Z",
        repo_root=repo,
    )
    # Both the public aggregate view and raw log directory can grow after the
    # cutoff without changing the as-of projection.
    frozen.write_text('{"future":"aggregate rewrite"}\n', encoding="utf-8")
    _write_jsonl(
        logs / "exp-20260607-001.json",
        [
            {
                "experiment_id": "exp-20260607-001",
                "timestamp": "2026-06-07T18:00:00Z",
                "trial_family": "future_family",
                "changed_variable": "future field",
                "status": "accepted",
            }
        ],
    )
    second = build_historical_prior_snapshot(
        frozen,
        history_cutoff="2026-06-06T00:00:00Z",
        repo_root=repo,
    )
    assert second == first
    assert validate_repository_historical_snapshot(first, repo_root=repo) == first


def test_repository_validation_rejects_isolated_fixture_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "frozen.jsonl"
    _write_jsonl(source, [_family()])
    snapshot = build_historical_prior_snapshot(
        source,
        history_cutoff="2026-06-06T00:00:00Z",
        isolated_fixture=True,
    )
    with pytest.raises(HistoricalPriorError, match="canonical_history_anchor_required"):
        validate_repository_historical_snapshot(snapshot, repo_root=tmp_path)


def test_rich_registry_sources_project_to_legacy_source_buckets() -> None:
    ohlcv = _muted_candidate()
    ohlcv["title"] = "Unclassified price state"
    ohlcv["hypothesis"] = "A price state may persist."
    ohlcv["fingerprint"]["component_sources"] = ["ohlcv_warehouse"]
    sources = {row["data_source"] for row in candidate_legacy_fingerprints(ohlcv)}
    assert {"ohlcv_warehouse", "ohlcv_relation", "ohlcv_momentum"} <= sources

    sec = _muted_candidate()
    sec["title"] = "Official filing event"
    sec["hypothesis"] = "A filing event changes the issuer state."
    sec["fingerprint"]["data_source"] = "sec_official_event"
    sec["fingerprint"]["component_sources"] = ["sec_official_event"]
    sec_sources = {row["data_source"] for row in candidate_legacy_fingerprints(sec)}
    assert "sec_text_event" in sec_sources


def test_canonical_open_ticket_projection_ignores_later_mutable_result(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    frozen = repo / "docs" / "frozen_families.jsonl"
    logs = repo / "experiments" / "logs"
    tickets = repo / "experiments" / "tickets"
    logs.mkdir(parents=True)
    tickets.mkdir(parents=True)
    frozen.parent.mkdir(parents=True)
    frozen.write_text("{}\n", encoding="utf-8")
    ticket_path = tickets / "exp-20260605-030.json"
    base_ticket = {
        "experiment_id": "exp-20260605-030",
        "created_at": "2026-06-05T12:00:00Z",
        "completed_at": "2026-06-07T12:00:00Z",
        "trial_family": "open_family",
        "hypothesis": "An open reservation tests a new state.",
        "single_causal_variable": "new state",
        "status": "claimed",
    }
    ticket_path.write_text(json.dumps(base_ticket), encoding="utf-8")
    first = build_historical_prior_snapshot(
        frozen,
        history_cutoff="2026-06-06T00:00:00Z",
        repo_root=repo,
    )
    mutated = {
        **base_ticket,
        "status": "rejected",
        "result": {"decision": "rejected", "realized_return": -0.5},
    }
    ticket_path.write_text(json.dumps(mutated), encoding="utf-8")
    second = build_historical_prior_snapshot(
        frozen,
        history_cutoff="2026-06-06T00:00:00Z",
        repo_root=repo,
    )
    assert second == first
    open_records = [row for row in first["records"] if row["origin"] == "open_ticket"]
    assert len(open_records) == 1
    assert open_records[0]["historical_status"] == "open_asof"
    assert open_records[0]["reopen_condition"] is None


def test_pre_cutoff_closeout_shard_closes_legacy_ticket_without_completed_at(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    frozen = repo / "docs" / "frozen_families.jsonl"
    logs = repo / "experiments" / "logs"
    tickets = repo / "experiments" / "tickets"
    logs.mkdir(parents=True)
    tickets.mkdir(parents=True)
    frozen.parent.mkdir(parents=True)
    frozen.write_text("{}\n", encoding="utf-8")
    ticket = {
        "experiment_id": "exp-20260605-031",
        "created_at": "2026-06-05T12:00:00Z",
        "completed_at": None,
        "trial_family": "legacy_ticket_without_close_clock",
        "hypothesis": "A reserved trial later closed.",
        "status": "claimed",
    }
    (tickets / "exp-20260605-031.json").write_text(
        json.dumps(ticket), encoding="utf-8"
    )
    closeout = {
        "experiment_id": "exp-20260605-031",
        "timestamp": "2026-06-05T15:00:00Z",
        "trial_family": "legacy_ticket_without_close_clock",
        "changed_variable": "closed_trial",
        "decision": "rejected",
    }
    (logs / "exp-20260605-031.json").write_text(
        json.dumps(closeout), encoding="utf-8"
    )

    snapshot = build_historical_prior_snapshot(
        frozen,
        history_cutoff="2026-06-06T00:00:00Z",
        repo_root=repo,
    )

    assert not [row for row in snapshot["records"] if row["origin"] == "open_ticket"]
    assert any(
        "exp-20260605-031" in row["representative_exps"]
        for row in snapshot["records"]
        if row["origin"] == "frozen_family"
    )


def test_post_cutoff_closeout_does_not_rewrite_open_asof_projection(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    frozen = repo / "docs" / "frozen_families.jsonl"
    logs = repo / "experiments" / "logs"
    tickets = repo / "experiments" / "tickets"
    logs.mkdir(parents=True)
    tickets.mkdir(parents=True)
    frozen.parent.mkdir(parents=True)
    frozen.write_text("{}\n", encoding="utf-8")
    ticket = {
        "experiment_id": "exp-20260605-032",
        "created_at": "2026-06-05T12:00:00Z",
        "completed_at": None,
        "trial_family": "open_at_cutoff",
        "hypothesis": "A reservation remains open at the historical cutoff.",
        "status": "claimed",
    }
    (tickets / "exp-20260605-032.json").write_text(
        json.dumps(ticket), encoding="utf-8"
    )
    first = build_historical_prior_snapshot(
        frozen,
        history_cutoff="2026-06-06T00:00:00Z",
        repo_root=repo,
    )
    (logs / "exp-20260605-032.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20260605-032",
                "timestamp": "2026-06-07T12:00:00Z",
                "trial_family": "open_at_cutoff",
                "changed_variable": "closed_later",
                "decision": "rejected",
            }
        ),
        encoding="utf-8",
    )
    second = build_historical_prior_snapshot(
        frozen,
        history_cutoff="2026-06-06T00:00:00Z",
        repo_root=repo,
    )

    assert second == first
    assert len([row for row in first["records"] if row["origin"] == "open_ticket"]) == 1


def _discovery_snapshot(tmp_path: Path, prior_candidate: dict) -> dict:
    source = tmp_path / "frozen.jsonl"
    ledger = tmp_path / "discovery.jsonl"
    _write_jsonl(source, [_family()])
    _write_jsonl(
        ledger,
        [
            {
                "record_type": "candidate_snapshot",
                "recorded_at": "2026-06-05T12:01:00Z",
                "payload": prior_candidate,
            }
        ],
    )
    return build_historical_prior_snapshot(
        source,
        history_cutoff="2026-06-06T00:00:00Z",
        discovery_ledgers=[ledger],
        isolated_fixture=True,
    )


def _no_core_prior_candidate() -> dict:
    return {
        "candidate_id": "cand-prior-continuation",
        "created_at": "2026-06-05T12:00:00Z",
        "title": "No-core basket continuation slot replacement",
        "hypothesis": (
            "A no-core basket replaces the scarce cash-feasible core slot when "
            "after-cost replacement value over ten sessions is positive under "
            "the broad market continuation ranking."
        ),
        "fingerprint": {
            "data_source": "massive_full_market_ohlcv",
            "component_sources": ["massive_full_market_ohlcv"],
            "expectation_proxy": "price_revealed",
            "economic_mechanism": "broad_market_continuation_opportunity_cost",
            "decision_surface": "candidate_pool",
            "payoff_shape": "cost_adjusted_slot_replacement_value",
            "horizon": "next_open_to_10_sessions",
            "execution_dependency": "next_session_open_fixed_exit",
            "portfolio_role": "scarce_cash_feasible_entry_slot_alternative",
        },
    }


def _split_event_candidate() -> dict:
    return {
        "title": "Forward split execution drift no-core basket",
        "hypothesis": (
            "Buying liquid active common stocks at the next session open after "
            "an official forward stock split execution date, with a fixed "
            "ten-session hold and round-trip costs, produces replacement value "
            "above the same-date core candidate or cash."
        ),
        "fingerprint": {
            "data_source": "massive_full_market_ohlcv",
            "component_sources": ["massive_full_market_ohlcv"],
            "expectation_proxy": "price_revealed",
            "economic_mechanism": "forward_split_execution_event_drift",
            "decision_surface": "candidate_pool",
            "payoff_shape": "cost_adjusted_slot_replacement_value",
            "horizon": "next_open_to_10_sessions",
            "execution_dependency": "next_session_open_fixed_exit",
            "portfolio_role": "scarce_cash_feasible_entry_slot_alternative",
        },
    }


def test_discovery_record_preserves_economic_mechanism(tmp_path: Path) -> None:
    snapshot = _discovery_snapshot(tmp_path, _no_core_prior_candidate())
    discovery = [
        row for row in snapshot["records"] if row["origin"] == "discovery_candidate"
    ]
    assert discovery
    assert all(
        row["fingerprint"].get("economic_mechanism")
        == "broad_market_continuation_opportunity_cost"
        for row in discovery
    )
    assert validate_historical_prior_snapshot(snapshot) == snapshot


def test_cross_mechanism_same_source_discovery_hit_is_waived(tmp_path: Path) -> None:
    # Same single source and shared no-core boilerplate push the score past
    # WARN, but the mechanisms are token-disjoint, so D3 must not treat the
    # second candidate family on the source as a duplicate (exp-20260728-005).
    snapshot = _discovery_snapshot(tmp_path, _no_core_prior_candidate())
    hits = legacy_near_neighbors(_split_event_candidate(), snapshot["records"])
    assert not [
        hit for hit in hits if hit["family_key"] == "cand-prior-continuation"
    ]


def test_same_mechanism_discovery_hit_still_rejects(tmp_path: Path) -> None:
    snapshot = _discovery_snapshot(tmp_path, _no_core_prior_candidate())
    retry = _split_event_candidate()
    retry["fingerprint"]["economic_mechanism"] = (
        "broad_market_continuation_opportunity_cost"
    )
    hits = legacy_near_neighbors(retry, snapshot["records"])
    assert [hit for hit in hits if hit["family_key"] == "cand-prior-continuation"]


def test_renamed_mechanism_with_overlapping_tokens_still_rejects(
    tmp_path: Path,
) -> None:
    # A cosmetic rename shares most mechanism tokens and must stay a duplicate.
    snapshot = _discovery_snapshot(tmp_path, _no_core_prior_candidate())
    retry = _split_event_candidate()
    retry["fingerprint"]["economic_mechanism"] = (
        "broad_market_continuation_opportunity_cost_v2"
    )
    hits = legacy_near_neighbors(retry, snapshot["records"])
    assert [hit for hit in hits if hit["family_key"] == "cand-prior-continuation"]


def test_structural_duplicate_score_rejects_despite_mechanism_rename(
    tmp_path: Path,
) -> None:
    # Near-verbatim text keeps the score at or above the structural bar, so a
    # fully renamed mechanism cannot hide a copied treatment.
    prior = _no_core_prior_candidate()
    snapshot = _discovery_snapshot(tmp_path, prior)
    copy = {
        "title": prior["title"],
        "hypothesis": prior["hypothesis"],
        "fingerprint": dict(
            prior["fingerprint"],
            economic_mechanism="renamed_disjoint_label_xyz",
        ),
    }
    hits = legacy_near_neighbors(copy, snapshot["records"])
    assert [hit for hit in hits if hit["family_key"] == "cand-prior-continuation"]


def test_missing_prior_mechanism_stays_conservative(tmp_path: Path) -> None:
    # Frozen-family records carry no mechanism; a cross-mechanism candidate
    # must still hit them (no waiver without explicit mechanisms on BOTH sides).
    source = tmp_path / "frozen.jsonl"
    _write_jsonl(source, [_family()])
    snapshot = build_historical_prior_snapshot(
        source, history_cutoff="2026-06-06T00:00:00Z", isolated_fixture=True
    )
    hits = legacy_near_neighbors(_muted_candidate(), snapshot["records"])
    assert hits


def _repo_with_ticket(tmp_path: Path, ticket: dict) -> Path:
    repo = tmp_path / "repo"
    frozen = repo / "docs" / "frozen_families.jsonl"
    (repo / "experiments" / "logs").mkdir(parents=True)
    tickets_dir = repo / "experiments" / "tickets"
    tickets_dir.mkdir(parents=True)
    frozen.parent.mkdir(parents=True, exist_ok=True)
    frozen.write_text("{}\n", encoding="utf-8")
    (tickets_dir / (ticket["experiment_id"] + ".json")).write_text(
        json.dumps(ticket), encoding="utf-8"
    )
    return repo


def test_stale_open_ticket_outside_window_is_not_a_discovery_prior(
    tmp_path: Path,
) -> None:
    # Mirrors the reserve-time in-flight guard: a months-old never-closed
    # ticket is stale coordination state and must not freeze discovery.
    repo = _repo_with_ticket(
        tmp_path,
        {
            "experiment_id": "exp-20260301-001",
            "created_at": "2026-03-01T12:00:00Z",
            "completed_at": None,
            "trial_family": "stale_shadow_entry",
            "hypothesis": "An opening-range continuation shadow entry.",
            "status": "proposed",
        },
    )
    snapshot = build_historical_prior_snapshot(
        repo / "docs" / "frozen_families.jsonl",
        history_cutoff="2026-06-06T00:00:00Z",
        repo_root=repo,
    )
    assert not [
        row for row in snapshot["records"] if row["origin"] == "open_ticket"
    ]


def test_fresh_open_ticket_inside_window_remains_a_discovery_prior(
    tmp_path: Path,
) -> None:
    repo = _repo_with_ticket(
        tmp_path,
        {
            "experiment_id": "exp-20260605-032",
            "created_at": "2026-06-05T12:00:00Z",
            "completed_at": None,
            "trial_family": "fresh_open_work",
            "hypothesis": "A reservation remains open at the historical cutoff.",
            "status": "claimed",
        },
    )
    snapshot = build_historical_prior_snapshot(
        repo / "docs" / "frozen_families.jsonl",
        history_cutoff="2026-06-06T00:00:00Z",
        repo_root=repo,
    )
    assert [row for row in snapshot["records"] if row["origin"] == "open_ticket"]


def test_measurement_repair_ticket_is_not_a_discovery_prior(tmp_path: Path) -> None:
    repo = _repo_with_ticket(
        tmp_path,
        {
            "experiment_id": "exp-20260605-033",
            "created_at": "2026-06-05T12:00:00Z",
            "completed_at": None,
            "lane": "measurement_repair",
            "trial_family": "guard_calibration_repair",
            "hypothesis": "Repair a guard calibration defect.",
            "status": "claimed",
        },
    )
    snapshot = build_historical_prior_snapshot(
        repo / "docs" / "frozen_families.jsonl",
        history_cutoff="2026-06-06T00:00:00Z",
        repo_root=repo,
    )
    assert not [
        row for row in snapshot["records"] if row["origin"] == "open_ticket"
    ]


def _massive_only_candidate() -> dict:
    # Declares massive plus the shared ohlcv price face; the legacy alias
    # expansion of ohlcv_warehouse then projects onto ohlcv_momentum and
    # ohlcv_relation, which are NOT declared faces. The synthetic pair below
    # scores 0.6235 against an ohlcv_momentum family — above WARN, below the
    # structural bar — reproducing the exp-20260728-005 blocker shape.
    candidate = _split_event_candidate()
    candidate["fingerprint"]["component_sources"] = [
        "massive_full_market_ohlcv",
        "ohlcv_warehouse",
    ]
    return candidate


def test_inferred_only_projection_hit_requires_structural_bar(tmp_path: Path) -> None:
    # ohlcv_momentum is reachable only through the legacy alias expansion of
    # a declared ohlcv face or text inference; a modest-similarity family
    # there must not hard-reject a candidate that never declared it.
    source = tmp_path / "frozen.jsonl"
    family = _family("exp-20260504-055")
    family["family_key"] = "broad_liquid_winner_continuation"
    family["fingerprint"] = {
        "data_source": "ohlcv_momentum",
        "field_tags": ["basket", "broad", "continuation", "liquid", "session", "winner"],
        "gate_shape": "candidate_pool_top1_10d",
    }
    _write_jsonl(source, [family])
    snapshot = build_historical_prior_snapshot(
        source, history_cutoff="2026-06-06T00:00:00Z", isolated_fixture=True
    )
    hits = legacy_near_neighbors(_massive_only_candidate(), snapshot["records"])
    assert not hits


def test_declared_component_face_hit_still_rejects(tmp_path: Path) -> None:
    # The same family on a source the candidate explicitly declares stays a
    # blocking near-neighbor at the reserve-time WARN calibration.
    source = tmp_path / "frozen.jsonl"
    family = _family("exp-20260504-056")
    family["family_key"] = "massive_prior_family"
    family["fingerprint"] = {
        "data_source": "massive_full_market_ohlcv",
        "field_tags": ["basket", "broad", "continuation", "liquid", "session", "winner"],
        "gate_shape": "candidate_pool_top1_10d",
    }
    _write_jsonl(source, [family])
    snapshot = build_historical_prior_snapshot(
        source, history_cutoff="2026-06-06T00:00:00Z", isolated_fixture=True
    )
    hits = legacy_near_neighbors(_massive_only_candidate(), snapshot["records"])
    assert [hit for hit in hits if hit["family_key"] == "massive_prior_family"]
