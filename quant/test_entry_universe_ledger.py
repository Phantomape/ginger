import json

import pytest

from quant.entry_universe_ledger import (
    BEFORE_FIRST_SNAPSHOT_POLICY,
    EntryUniverseResolver,
    MembershipSnapshotConflictError,
    MembershipSnapshotValidationError,
    append_membership_snapshot,
    build_membership_snapshot,
    load_membership_snapshots,
    membership_hash,
    validate_membership_snapshot,
)


def _snapshot(
    as_of="2026-07-17",
    tickers=("MSFT", "AAPL"),
    *,
    generated_at="2026-07-17T16:00:00Z",
    source="test_git_manifest",
    source_hash="abc123",
    clean_cutoff=None,
    provenance=None,
):
    return build_membership_snapshot(
        effective_as_of=as_of,
        tickers=tickers,
        generated_at=generated_at,
        source=source,
        source_hash=source_hash,
        clean_cutoff=clean_cutoff,
        provenance=provenance or {"experiment_id": "exp-20260717-003"},
    )


def test_build_snapshot_is_full_canonical_membership_and_hashes_are_stable():
    first = _snapshot(tickers=[" msft ", "AAPL", "aapl"])
    rerun = _snapshot(
        tickers=["AAPL", "MSFT"],
        generated_at="2026-07-17T17:05:00-04:00",
    )

    assert first["snapshot_semantics"] == "full_membership_replace"
    assert first["tickers"] == ["AAPL", "MSFT"]
    assert first["ticker_count"] == 2
    assert first["membership_hash"] == membership_hash(["MSFT", "AAPL"])
    # Operational generation time is not semantic membership identity.
    assert first["snapshot_hash"] == rerun["snapshot_hash"]
    assert first["record_hash"] != rerun["record_hash"]
    assert validate_membership_snapshot(first) == first


def test_append_is_atomic_semantic_idempotent_and_preserves_first_record(tmp_path):
    path = tmp_path / "membership.jsonl"
    first_snapshot = _snapshot()
    rerun_snapshot = _snapshot(generated_at="2026-07-18T01:00:00Z")

    first = append_membership_snapshot(path, first_snapshot)
    second = append_membership_snapshot(path, rerun_snapshot)

    assert first["status"] == "appended"
    assert second["status"] == "duplicate"
    assert first["snapshot_hash"] == second["snapshot_hash"]
    assert second["record_hash"] == first_snapshot["record_hash"]
    assert second["generated_at"] == first_snapshot["generated_at"]
    assert first["snapshot_count"] == second["snapshot_count"] == 1
    assert first["ledger_hash"] == second["ledger_hash"]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert not (tmp_path / "membership.jsonl.lock").exists()


def test_same_day_membership_conflict_fails_closed_without_changing_file(tmp_path):
    path = tmp_path / "membership.jsonl"
    append_membership_snapshot(path, _snapshot(tickers=["AAPL"]))
    before = path.read_bytes()

    with pytest.raises(MembershipSnapshotConflictError, match="2026-07-17"):
        append_membership_snapshot(path, _snapshot(tickers=["AAPL", "MSFT"]))

    assert path.read_bytes() == before
    assert EntryUniverseResolver.from_path(path)("2026-07-17") == {"AAPL"}


def test_same_membership_but_changed_stable_provenance_is_a_conflict(tmp_path):
    path = tmp_path / "membership.jsonl"
    append_membership_snapshot(
        path,
        _snapshot(provenance={"generation": "broad_market_clean_forward_v1"}),
    )

    with pytest.raises(MembershipSnapshotConflictError):
        append_membership_snapshot(
            path,
            _snapshot(provenance={"generation": "different_contract"}),
        )


def test_load_validates_hashes_and_reports_line_number_for_bad_json(tmp_path):
    path = tmp_path / "membership.jsonl"
    row = _snapshot()
    row["tickers"].append("NVDA")
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(MembershipSnapshotValidationError, match="hash mismatch|ticker_count"):
        load_membership_snapshots(path)

    path.write_text("{not-json}\n", encoding="utf-8")
    with pytest.raises(MembershipSnapshotValidationError, match=r":1"):
        load_membership_snapshots(path)


def test_load_rejects_duplicate_physical_rows_even_when_semantically_identical(tmp_path):
    path = tmp_path / "membership.jsonl"
    row = _snapshot()
    line = json.dumps(row, sort_keys=True)
    path.write_text(f"{line}\n{line}\n", encoding="utf-8")

    with pytest.raises(
        MembershipSnapshotValidationError, match="duplicate physical snapshot"
    ):
        load_membership_snapshots(path)


def test_resolver_is_unknown_empty_before_first_then_uses_latest_full_snapshot(tmp_path):
    path = tmp_path / "membership.jsonl"
    append_membership_snapshot(
        path,
        _snapshot("2026-01-10", ["AAPL", "MSFT"], generated_at="2026-01-10T23:00:00Z"),
    )
    append_membership_snapshot(
        path,
        _snapshot("2026-02-01", ["MSFT", "NVDA"], generated_at="2026-02-01T23:00:00Z"),
    )
    resolver = EntryUniverseResolver.from_path(path)

    assert resolver("2026-01-09") == set()
    assert resolver.resolve("2026-01-09")["status"] == "unknown_before_first_snapshot"
    assert resolver("2026-01-10") == {"AAPL", "MSFT"}
    assert resolver("2026-01-31") == {"AAPL", "MSFT"}
    assert resolver("2026-02-01") == {"MSFT", "NVDA"}
    assert resolver("2027-01-01") == {"MSFT", "NVDA"}
    # Removed tickers remain in the preload union so historical bars are not lost.
    assert resolver.data_tickers == frozenset({"AAPL", "MSFT", "NVDA"})

    resolved = resolver.resolve("2026-02-10")
    assert resolved["effective_as_of"] == "2026-02-01"
    assert resolved["source"] == "test_git_manifest"
    assert resolved["provenance"]["experiment_id"] == "exp-20260717-003"


def test_explicit_empty_snapshot_is_known_empty_not_unknown():
    resolver = EntryUniverseResolver(
        [_snapshot("2026-01-10", [], generated_at="2026-01-10T23:00:00Z")]
    )

    before = resolver.resolve("2026-01-09")
    on_date = resolver.resolve("2026-01-10")

    assert before["status"] == "unknown_before_first_snapshot"
    assert on_date["status"] == "resolved"
    assert on_date["tickers"] == []
    assert on_date["membership_hash"] == membership_hash([])


def test_empty_ledger_metadata_is_explicit_and_detached(tmp_path):
    resolver = EntryUniverseResolver.from_path(tmp_path / "missing.jsonl")
    metadata = resolver.metadata

    assert resolver("2026-01-01") == set()
    assert resolver.resolve("2026-01-01")["status"] == "unknown_empty_ledger"
    assert metadata["before_first_snapshot_policy"] == BEFORE_FIRST_SNAPSHOT_POLICY
    assert metadata["snapshot_count"] == 0
    assert metadata["data_ticker_count"] == 0
    metadata["snapshot_count"] = 99
    assert resolver.metadata["snapshot_count"] == 0


def test_metadata_carries_clean_cutoff_union_hashes_and_snapshot_provenance(tmp_path):
    path = tmp_path / "membership.jsonl"
    snapshot = _snapshot(
        clean_cutoff="2026-07-17",
        provenance={
            "generation": "broad_market_clean_forward_v1",
            "experiment_id": "exp-20260717-003",
        },
    )
    append_membership_snapshot(path, snapshot)
    metadata = EntryUniverseResolver.from_path(path).metadata

    assert metadata["first_effective_as_of"] == "2026-07-17"
    assert metadata["last_effective_as_of"] == "2026-07-17"
    assert metadata["data_tickers_hash"] == membership_hash(["AAPL", "MSFT"])
    assert metadata["ledger_hash"]
    assert metadata["ledger_record_hash"]
    assert metadata["snapshots"][0]["clean_cutoff"] == "2026-07-17"
    assert (
        metadata["snapshots"][0]["provenance"]["generation"]
        == "broad_market_clean_forward_v1"
    )


@pytest.mark.parametrize(
    "mutation, match",
    [
        (lambda row: row.update({"extra": True}), "unknown fields"),
        (lambda row: row.update({"generated_at": "2026-07-17T12:00:00"}), "timezone"),
        (lambda row: row.update({"tickers": ["MSFT", "AAPL"]}), "sorted"),
    ],
)
def test_validation_rejects_noncanonical_or_extended_rows(mutation, match):
    row = _snapshot()
    mutation(row)

    with pytest.raises(MembershipSnapshotValidationError, match=match):
        validate_membership_snapshot(row)
