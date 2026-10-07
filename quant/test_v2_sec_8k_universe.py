from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest

import quant.v2_universe_observation as universe_observation_module
import quant.v2_sec_8k_runtime_adapter as runtime_adapter_module
import quant.v2_sec_8k_universe as sec_8k_module
import quant.v2_universe_ledger_segments as segments_module
from quant.v2_contracts import canonical_hash, canonical_json
from quant.v2_universe_observation import (
    V2UniverseObservationError,
    observe_sec_8k_daily_universe,
    observe_sec_8k_replay_universe,
    observe_sec_8k_universe,
)
from quant.v2_sec_8k_universe import (
    V2SEC8KUniverseError,
    build_sec_8k_materialization,
    create_source_bundle_manifest,
    freeze_sec_8k_source_bundle,
    publish_sec_8k_materialization,
    validate_persisted_sec_8k_materialization,
)
from quant.v2_sec_8k_runtime_adapter import (
    LEDGER_BACKEND_LEGACY_JSONL_V1,
    LEDGER_BACKEND_SEGMENTED_HOT_V1,
    V2SEC8KRuntimeAdapterError,
    read_sec_8k_daily_runtime_universe,
    read_sec_8k_replay_runtime_universe,
    read_sec_8k_runtime_universe,
)
from quant.v2_universe_ledger import load_v2_universe_ledger
from quant.v2_universe_ledger_segments import (
    COMPACT_HEAD_STORAGE_CONTRACT,
    STORAGE_CONTRACT,
    build_segmented_ledger_contract,
    rotate_segmented_v2_universe_checkpoint,
    segmented_record_path,
)


FORM_DATE = "20260820"
FROZEN_AT = "2026-08-21T12:30:00Z"
ARTIFACT_TIMES = {
    "sec_access.html": "2026-08-21T12:10:00Z",
    "sec_webmaster_faq.html": "2026-08-21T12:11:00Z",
    "sec_edgar_calendar.html": "2026-08-21T12:12:00Z",
    f"form.{FORM_DATE}.idx": "2026-08-21T12:13:00Z",
    "company_tickers_exchange.json": "2026-08-21T12:14:00Z",
}
RETRIEVAL_METADATA = {
    filename: {
        "http_status": 200,
        "request_headers": {
            "User-Agent": "ginger-v2-test tests@example.com",
            "Accept-Encoding": "identity",
        },
        "response_headers": {},
    }
    for filename in ARTIFACT_TIMES
}


def _index_row(form, company, cik, filed, path):
    return f"{form:<12}{company:<62}{cik:<12}{filed:<12}{path}"


def _source_bundle(tmp_path: Path) -> Path:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "sec_access.html").write_text(
        """
        <html><body>
        <h1>Accessing EDGAR Data</h1>
        <p>EDGAR accepts new filer submissions, test filings, and correspondence
        from 6:00 a.m. to 10:00 p.m., ET, Monday through Friday, except federal
        holidays.</p>
        <p>Current max request rate: 10 requests/second.</p>
        <p>Daily index files are available, and company_tickers_exchange.json
        contains ticker and exchange associations.</p>
        </body></html>
        """,
        encoding="utf-8",
    )
    (source_dir / "sec_webmaster_faq.html").write_text(
        """
        <html><body><h1>Webmaster Frequently Asked Questions</h1>
        <p>SEC.gov content and EDGAR filings are free to access and reuse,
        including for investment research. Automated scripted access must
        declare a User-Agent and remain at or below 10 requests per second.</p>
        </body></html>
        """,
        encoding="utf-8",
    )
    (source_dir / "sec_edgar_calendar.html").write_text(
        """
        <html><body><h1>2026 EDGAR Filing Calendar</h1>
        <p>EDGAR will not accept filings on the following federal holidays.</p>
        <h2>Federal Holidays in 2026</h2>
        <table>
        <tr><td>Thursday, January 1, 2026</td><td>2026-01-01</td><td>New Year's Day</td></tr>
        <tr><td>Monday, January 19, 2026</td><td>2026-01-19</td><td>Birthday of Martin Luther King, Jr.</td></tr>
        <tr><td>Monday, February 16, 2026</td><td>2026-02-16</td><td>Washington's Birthday</td></tr>
        <tr><td>Monday, May 25, 2026</td><td>2026-05-25</td><td>Memorial Day</td></tr>
        <tr><td>Friday, June 19, 2026</td><td>2026-06-19</td><td>Juneteenth National Independence Day</td></tr>
        <tr><td>Friday, July 3, 2026</td><td>2026-07-03</td><td>Independence Day observed</td></tr>
        <tr><td>Monday, September 7, 2026</td><td>2026-09-07</td><td>Labor Day</td></tr>
        <tr><td>Monday, October 12, 2026</td><td>2026-10-12</td><td>Columbus Day</td></tr>
        <tr><td>Wednesday, November 11, 2026</td><td>2026-11-11</td><td>Veterans Day</td></tr>
        <tr><td>Thursday, November 26, 2026</td><td>2026-11-26</td><td>Thanksgiving Day</td></tr>
        <tr><td>Friday, December 25, 2026</td><td>2026-12-25</td><td>Christmas Day</td></tr>
        </table>
        <h2>Peak Filings</h2>
        </body></html>
        """,
        encoding="utf-8",
    )
    index_rows = [
        "Description:           Daily Index of EDGAR Dissemination Feed by Form Type",
        "Last Data Received:    Aug 20, 2026",
        "Form Type   Company Name                                                   CIK         Date Filed  File Name",
        "-" * 120,
        _index_row(
            "8-K",
            "Alpha Incorporated",
            "1001",
            "20260820",
            "edgar/data/1001/0000001001-26-000001.txt",
        ),
        _index_row(
            "8-K",
            "Alpha Incorporated",
            "1001",
            "20260819",
            "edgar/data/1001/0000001001-26-000002.txt",
        ),
        _index_row(
            "8-K",
            "Missing Association Corp",
            "1002",
            "20260820",
            "edgar/data/1002/0000001002-26-000001.txt",
        ),
        _index_row(
            "8-K",
            "Ambiguous Association Corp",
            "1003",
            "20260820",
            "edgar/data/1003/0000001003-26-000001.txt",
        ),
        _index_row(
            "8-K",
            "Unsupported Venue Corp",
            "1004",
            "20260820",
            "edgar/data/1004/0000001004-26-000001.txt",
        ),
        _index_row(
            "8-K/A",
            "Amended Filing Is Out Of Scope",
            "1005",
            "20260820",
            "edgar/data/1005/0000001005-26-000001.txt",
        ),
        _index_row(
            "10-K",
            "Other Form Is Out Of Scope",
            "1006",
            "20260820",
            "edgar/data/1006/0000001006-26-000001.txt",
        ),
    ]
    (source_dir / f"form.{FORM_DATE}.idx").write_text(
        "\n".join(index_rows) + "\n", encoding="utf-8"
    )
    (source_dir / "company_tickers_exchange.json").write_text(
        json.dumps(
            {
                "fields": ["cik", "name", "ticker", "exchange"],
                "data": [
                    [1001, "Alpha Incorporated", "AAA", "Nasdaq"],
                    [1003, "Ambiguous Association Corp", "AMB", "Nasdaq"],
                    [1003, "Ambiguous Association Corp Class B", "AM.B", "NYSE"],
                    [1004, "Unsupported Venue Corp", "OTCX", "OTC"],
                    [1005, "Amended Filing Is Out Of Scope", "AMD", "Nasdaq"],
                ],
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    create_source_bundle_manifest(
        source_dir,
        FORM_DATE,
        ARTIFACT_TIMES,
        FROZEN_AT,
        retrieval_metadata_by_artifact=RETRIEVAL_METADATA,
    )
    return source_dir


def _mapping_evidence(envelope):
    return [
        item
        for item in envelope["evidence_records"]
        if item["security_mapping"] is not None
    ]


def _replace_mapping_surface(source_dir: Path, rows: list[list[object]]) -> None:
    (source_dir / "bundle.json").unlink()
    (source_dir / "company_tickers_exchange.json").write_text(
        json.dumps(
            {
                "fields": ["cik", "name", "ticker", "exchange"],
                "data": rows,
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    create_source_bundle_manifest(
        source_dir,
        FORM_DATE,
        ARTIFACT_TIMES,
        FROZEN_AT,
        retrieval_metadata_by_artifact=RETRIEVAL_METADATA,
    )


def _published_runtime_fixture(tmp_path):
    source_dir = _source_bundle(tmp_path)
    ledger_path = tmp_path / "runtime" / "universe.jsonl"
    envelope_path = tmp_path / "runtime" / "materialization.json"
    publish_sec_8k_materialization(source_dir, ledger_path, envelope_path)
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    return (
        source_dir,
        ledger_path,
        envelope_path,
        envelope["universe_manifest"]["manifest_id"],
        envelope["universe_manifest"]["membership_as_of"],
    )


def _read_runtime_fixture(source_dir, ledger_path, envelope_path, manifest_id, as_of):
    return read_sec_8k_runtime_universe(
        source_dir,
        envelope_path,
        backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
        storage_location=ledger_path,
        manifest_id=manifest_id,
        as_of=as_of,
    )


def _write_segmented_runtime_store(root, ledger_path):
    contract = build_segmented_ledger_contract(load_v2_universe_ledger(ledger_path))
    checkpoint = contract["checkpoint"]
    checkpoint_path = segmented_record_path(
        root, "checkpoint", checkpoint["checkpoint_hash"]
    )
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_bytes((canonical_json(checkpoint) + "\n").encode("utf-8"))
    for segment in contract["segments"]:
        segment_path = segmented_record_path(
            root, "segment", segment["segment_hash"]
        )
        segment_path.parent.mkdir(parents=True, exist_ok=True)
        segment_path.write_bytes((canonical_json(segment) + "\n").encode("utf-8"))
    (root / "HEAD.json").write_bytes(
        (canonical_json(contract["head"]) + "\n").encode("utf-8")
    )
    return root


def _reseal_runtime_snapshot(runtime, *, refresh_membership_semantics):
    membership = runtime["membership_snapshot"]
    if refresh_membership_semantics:
        semantic_rows = [
            {key: value for key, value in row.items() if key != "latest_event_hash"}
            for row in membership["memberships"]
        ]
        semantic_hash = canonical_hash(semantic_rows)
        membership["membership_snapshot_sha256"] = semantic_hash
        runtime["membership_snapshot_sha256"] = semantic_hash
    membership_payload = dict(membership)
    membership_payload.pop("snapshot_hash")
    membership["snapshot_hash"] = canonical_hash(membership_payload)
    runtime["shared_reader_snapshot_hash"] = membership["snapshot_hash"]
    runtime_payload = dict(runtime)
    runtime_payload.pop("adapter_snapshot_hash")
    runtime["adapter_snapshot_hash"] = canonical_hash(runtime_payload)


def _assert_resealed_observation_rejected(
    tmp_path,
    monkeypatch,
    mutate,
    *,
    code,
    refresh_membership_semantics,
):
    source_dir, ledger_path, envelope_path, manifest_id, as_of = (
        _published_runtime_fixture(tmp_path)
    )
    runtime = _read_runtime_fixture(
        source_dir, ledger_path, envelope_path, manifest_id, as_of
    )
    mutate(runtime)
    _reseal_runtime_snapshot(
        runtime,
        refresh_membership_semantics=refresh_membership_semantics,
    )
    monkeypatch.setattr(
        universe_observation_module,
        "read_sec_8k_runtime_universe",
        lambda *args, **kwargs: runtime,
    )
    with pytest.raises(V2UniverseObservationError) as caught:
        observe_sec_8k_universe(
            source_dir,
            envelope_path,
            backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
            storage_location=ledger_path,
            manifest_id=manifest_id,
            as_of=as_of,
        )
    assert caught.value.code == code


def test_build_strictly_enumerates_dispositions_and_deduplicates_active_identity(
    tmp_path, monkeypatch,
):
    source_dir = _source_bundle(tmp_path)
    assert freeze_sec_8k_source_bundle(
        source_dir, FORM_DATE, "ginger-v2-test tests@example.com"
    )["status"] == "duplicate"
    envelope = build_sec_8k_materialization(source_dir)
    copied_source = tmp_path / "copied-source"
    shutil.copytree(source_dir, copied_source)
    assert build_sec_8k_materialization(copied_source)["envelope_hash"] == envelope[
        "envelope_hash"
    ]
    monkeypatch.chdir(tmp_path)
    assert build_sec_8k_materialization(Path("source"))["envelope_hash"] == envelope[
        "envelope_hash"
    ]
    locator_prefix = f"bundle:{envelope['input_bundle_id']}/"
    for evidence in envelope["evidence_records"]:
        assert evidence["raw_artifact_locator"].startswith(locator_prefix)
        artifact = source_dir / evidence["raw_artifact_locator"][len(locator_prefix) :]
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == evidence[
            "raw_artifact_sha256"
        ]
    (copied_source / "bundle.json").unlink()
    refetch_times = {
        filename: instant.replace("12:1", "12:2")
        for filename, instant in ARTIFACT_TIMES.items()
    }
    refetch_metadata = json.loads(json.dumps(RETRIEVAL_METADATA))
    for item in refetch_metadata.values():
        item["request_headers"]["User-Agent"] = "ginger-v2-refetch refetch@example.com"
    create_source_bundle_manifest(
        copied_source,
        FORM_DATE,
        refetch_times,
        "2026-08-21T12:40:00Z",
        retrieval_metadata_by_artifact=refetch_metadata,
    )
    refetched = build_sec_8k_materialization(copied_source)
    assert [row["source_row_sha256"] for row in refetched["coverage_snapshot"]["rows"]] == [
        row["source_row_sha256"] for row in envelope["coverage_snapshot"]["rows"]
    ]
    assert refetched["envelope_hash"] != envelope["envelope_hash"]
    coverage = envelope["coverage_snapshot"]
    manifest = envelope["universe_manifest"]
    rows = coverage["rows"]

    assert len(rows) == 5
    assert coverage["source_reported_row_count"] == 5
    assert coverage["disposition_counts"] == {
        "excluded": 1,
        "mapped": 2,
        "unmapped": 2,
    }
    assert len({item["source_row_id"] for item in rows}) == len(rows)
    assert len({item["source_row_sha256"] for item in rows}) == len(rows)
    assert [item["source_row_id"] for item in rows] == sorted(
        item["source_row_id"] for item in rows
    )

    unmapped_reasons = [
        item["reason_code"] for item in rows if item["disposition"] == "unmapped"
    ]
    assert any("missing" in reason for reason in unmapped_reasons)
    assert any("ambiguous" in reason for reason in unmapped_reasons)
    excluded_reasons = [
        item["reason_code"] for item in rows if item["disposition"] == "excluded"
    ]
    assert len(excluded_reasons) == 1
    assert "unsupported" in excluded_reasons[0]

    mapped_rows = [item for item in rows if item["disposition"] == "mapped"]
    assert len({item["security_mapping"]["mapping_id"] for item in mapped_rows}) == 1
    assert len(_mapping_evidence(envelope)) == 1
    assert len(envelope["universe_events"]) == 1
    assert len(manifest["memberships"]) == 1
    assert {
        (item["security_id"], item["listing_id"], item["mapping_sha256"])
        for item in manifest["memberships"]
    } == {
        (
            item["security_mapping"]["security_id"],
            item["security_mapping"]["listing_id"],
            item["security_mapping"]["mapping_sha256"],
        )
        for item in mapped_rows
    }

    expected_boundary = {
        "pit_tier": "research_pit",
        "external_universe_coverage_status": "unverified",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "parity_status": "contract_only_unwired",
        "authority": "research_only",
        "trade_enabled": False,
    }
    assert {
        key: envelope["boundary"][key] for key in expected_boundary
    } == expected_boundary
    for record in (coverage, manifest):
        assert record["pit_tier"] == "research_pit"
        assert record["external_universe_coverage_status"] == "unverified"
        assert record["result_ceiling"] == "observed_only"
        assert record["paper_live_eligible"] is False
        assert record["parity_status"] == "contract_only_unwired"
        assert record["authority"] == "research_only"
        assert record["trade_enabled"] is False


def test_all_unmapped_or_excluded_surface_publishes_known_empty_active_universe(
    tmp_path,
):
    source_dir = _source_bundle(tmp_path)
    baseline = build_sec_8k_materialization(source_dir)
    _replace_mapping_surface(
        source_dir,
        [[1004, "Unsupported Venue Corp", "OTCX", "OTC"]],
    )
    envelope = build_sec_8k_materialization(source_dir)
    assert {
        row["source_row_id"]: row["source_row_sha256"]
        for row in envelope["coverage_snapshot"]["rows"]
    } == {
        row["source_row_id"]: row["source_row_sha256"]
        for row in baseline["coverage_snapshot"]["rows"]
    }
    assert envelope["coverage_snapshot"]["disposition_counts"] == {
        "excluded": 1,
        "mapped": 0,
        "unmapped": 4,
    }
    assert envelope["universe_events"] == []
    assert envelope["universe_manifest"]["memberships"] == []

    ledger_path = tmp_path / "empty-active" / "universe.jsonl"
    envelope_path = tmp_path / "empty-active" / "materialization.json"
    result = publish_sec_8k_materialization(source_dir, ledger_path, envelope_path)
    assert result["status"] == "committed"
    validate_persisted_sec_8k_materialization(source_dir, ledger_path, envelope_path)


@pytest.mark.parametrize(
    "artifact_name",
    (f"form.{FORM_DATE}.idx", "company_tickers_exchange.json", "sec_edgar_calendar.html"),
)
def test_build_rejects_raw_artifact_tampering(tmp_path, artifact_name):
    source_dir = _source_bundle(tmp_path)
    artifact = source_dir / artifact_name
    artifact.write_bytes(artifact.read_bytes() + b"\npost-freeze tamper")

    with pytest.raises(V2SEC8KUniverseError) as caught:
        build_sec_8k_materialization(source_dir)
    assert any(
        token in caught.value.code for token in ("conflict", "mismatch", "sha256")
    )


def test_bundle_rejects_same_day_daily_index_as_incomplete(tmp_path):
    source_dir = _source_bundle(tmp_path)
    (source_dir / "bundle.json").unlink()
    (source_dir / f"form.{FORM_DATE}.idx").rename(source_dir / "form.20260821.idx")
    same_day_times = dict(ARTIFACT_TIMES)
    same_day_times["form.20260821.idx"] = same_day_times.pop(f"form.{FORM_DATE}.idx")
    same_day_metadata = json.loads(json.dumps(RETRIEVAL_METADATA))
    same_day_metadata["form.20260821.idx"] = same_day_metadata.pop(
        f"form.{FORM_DATE}.idx"
    )

    with pytest.raises(V2SEC8KUniverseError) as caught:
        create_source_bundle_manifest(
            source_dir,
            "20260821",
            same_day_times,
            FROZEN_AT,
            retrieval_metadata_by_artifact=same_day_metadata,
        )
    assert caught.value.code == "daily_index_not_complete"


def test_publish_is_idempotent_and_persisted_graph_revalidates(tmp_path):
    source_dir = _source_bundle(tmp_path)
    ledger_path = tmp_path / "published" / "universe.jsonl"
    envelope_path = tmp_path / "published" / "materialization.json"

    first = publish_sec_8k_materialization(source_dir, ledger_path, envelope_path)
    second = publish_sec_8k_materialization(source_dir, ledger_path, envelope_path)
    verified = validate_persisted_sec_8k_materialization(
        source_dir, ledger_path, envelope_path
    )

    assert first["status"] == "committed"
    assert first["ledger_status"] == "appended"
    assert first["envelope_status"] == "committed"
    assert second["status"] == "duplicate"
    assert second["ledger_status"] == "duplicate"
    assert second["envelope_status"] == "duplicate"
    assert second["envelope_hash"] == first["envelope_hash"]
    assert verified["envelope_hash"] == first["envelope_hash"]


def test_runtime_adapter_verifies_materialization_and_uses_one_daily_replay_reader(
    tmp_path,
):
    source_dir = _source_bundle(tmp_path)
    ledger_path = tmp_path / "runtime" / "universe.jsonl"
    envelope_path = tmp_path / "runtime" / "materialization.json"
    publish_sec_8k_materialization(source_dir, ledger_path, envelope_path)
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    manifest_id = envelope["universe_manifest"]["manifest_id"]
    as_of = envelope["universe_manifest"]["membership_as_of"]

    runtime = read_sec_8k_runtime_universe(
        source_dir,
        envelope_path,
        backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
        storage_location=ledger_path,
        manifest_id=manifest_id,
        as_of=as_of,
    )
    daily = read_sec_8k_daily_runtime_universe(
        source_dir,
        envelope_path,
        backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
        storage_location=ledger_path,
        manifest_id=manifest_id,
        as_of=as_of,
    )
    copied_source = tmp_path / "copied-source"
    copied_runtime = tmp_path / "copied-runtime"
    shutil.copytree(source_dir, copied_source)
    shutil.copytree(ledger_path.parent, copied_runtime)
    replay = read_sec_8k_replay_runtime_universe(
        copied_source,
        copied_runtime / envelope_path.name,
        backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
        storage_location=copied_runtime / ledger_path.name,
        manifest_id=manifest_id,
        as_of="2026-08-21T05:30:00-07:00",
    )

    assert read_sec_8k_daily_runtime_universe is read_sec_8k_runtime_universe
    assert read_sec_8k_replay_runtime_universe is read_sec_8k_runtime_universe
    assert runtime == daily == replay
    assert runtime["schema_version"] == 3
    assert runtime["adapter_contract"] == "v2_sec_8k_runtime_universe_adapter_v3"
    assert runtime["ledger_backend"] == LEDGER_BACKEND_LEGACY_JSONL_V1
    assert runtime["segmented_hot_state_identity"] is None
    assert runtime["input_identity"]["ledger_backend"] == LEDGER_BACKEND_LEGACY_JSONL_V1
    assert runtime["input_identity"]["segmented_hot_state_identity_sha256"] is None
    assert runtime["adapter_parity_status"] == "daily_replay_verified_research_only"
    assert runtime["input_identity"]["as_of"] == "2026-08-21T12:30:00Z"
    assert runtime["input_identity_sha256"] == canonical_hash(runtime["input_identity"])
    assert (
        runtime["shared_reader_snapshot_hash"]
        == runtime["membership_snapshot"]["snapshot_hash"]
    )
    payload = dict(runtime)
    supplied_hash = payload.pop("adapter_snapshot_hash")
    assert supplied_hash == canonical_hash(payload)
    assert runtime["membership_count"] == 1
    assert (
        runtime["membership_snapshot"]["memberships"][0]["security_id"]
        == "sec-association-0000001001-aaa"
    )
    assert runtime["membership_snapshot"]["trade_enabled"] is False
    assert runtime["membership_snapshot"]["paper_live_eligible"] is False
    assert runtime["membership_snapshot"]["parity_status"] == "contract_only_unwired"
    assert runtime["boundary"] == {
        "external_universe_coverage_status": "unverified",
        "pit_tier": "research_pit",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "parity_status": "contract_only_unwired",
        "authority": "research_only",
        "trade_enabled": False,
    }


@pytest.mark.parametrize(
    ("compact", "expected_contract", "legacy_compatible"),
    (
        (False, STORAGE_CONTRACT, True),
        (True, COMPACT_HEAD_STORAGE_CONTRACT, False),
    ),
    ids=("full-checkpoint", "compact-checkpoint"),
)
def test_segmented_hot_runtime_uses_one_state_load_without_archive_or_legacy_fallback(
    tmp_path, monkeypatch, compact, expected_contract, legacy_compatible
):
    source_dir, ledger_path, envelope_path, manifest_id, as_of = (
        _published_runtime_fixture(tmp_path)
    )
    legacy = _read_runtime_fixture(
        source_dir, ledger_path, envelope_path, manifest_id, as_of
    )
    segmented_root = _write_segmented_runtime_store(
        tmp_path / "segmented-runtime", ledger_path
    )
    if compact:
        rotate_segmented_v2_universe_checkpoint(segmented_root)
    copied_source = tmp_path / "copied-segmented-source"
    copied_envelope = tmp_path / "copied-segmented-materialization.json"
    copied_segmented_root = tmp_path / "copied-segmented-runtime"
    shutil.copytree(source_dir, copied_source)
    shutil.copy2(envelope_path, copied_envelope)
    shutil.copytree(segmented_root, copied_segmented_root)

    real_hot_load = runtime_adapter_module.load_segmented_v2_universe_state
    hot_loads = []

    def counted_hot_load(storage_location):
        hot_loads.append(Path(storage_location))
        return real_hot_load(storage_location)

    def forbidden_path(*args, **kwargs):
        raise AssertionError("segmented-hot runtime used a legacy or exact path")

    monkeypatch.setattr(
        runtime_adapter_module,
        "load_segmented_v2_universe_state",
        counted_hot_load,
    )
    monkeypatch.setattr(
        runtime_adapter_module,
        "validate_persisted_sec_8k_materialization",
        forbidden_path,
    )
    monkeypatch.setattr(
        runtime_adapter_module,
        "read_v2_universe_membership",
        forbidden_path,
    )
    monkeypatch.setattr(segments_module, "_load_exact_generations", forbidden_path)

    runtime = read_sec_8k_daily_runtime_universe(
        source_dir,
        envelope_path,
        backend=LEDGER_BACKEND_SEGMENTED_HOT_V1,
        storage_location=segmented_root,
        manifest_id=manifest_id,
        as_of=as_of,
    )
    replay = read_sec_8k_replay_runtime_universe(
        copied_source,
        copied_envelope,
        backend=LEDGER_BACKEND_SEGMENTED_HOT_V1,
        storage_location=copied_segmented_root,
        manifest_id=manifest_id,
        as_of="2026-08-21T05:30:00-07:00",
    )

    assert hot_loads == [segmented_root, copied_segmented_root]
    assert read_sec_8k_daily_runtime_universe is read_sec_8k_runtime_universe
    assert read_sec_8k_replay_runtime_universe is read_sec_8k_runtime_universe
    assert runtime == replay
    assert runtime["membership_snapshot"] == legacy["membership_snapshot"]
    assert runtime["ledger_backend"] == LEDGER_BACKEND_SEGMENTED_HOT_V1
    hot_identity = runtime["segmented_hot_state_identity"]
    assert hot_identity["storage_contract"] == expected_contract
    assert hot_identity["legacy_full_reader_compatible"] is legacy_compatible
    assert hot_identity["head_manifest_id"] == manifest_id
    assert hot_identity["head_manifest_hash"] == runtime["input_identity"][
        "manifest_hash"
    ]
    assert runtime["input_identity"][
        "segmented_hot_state_identity_sha256"
    ] == canonical_hash(hot_identity)
    assert runtime["trade_enabled"] is False
    assert runtime["membership_snapshot"]["trade_enabled"] is False


def test_checked_in_sec_graph_segmented_hot_matches_legacy_runtime(tmp_path):
    repository = Path(__file__).resolve().parents[1]
    source_dir = (
        repository
        / "data/v2/source_bundles/sec_edgar_8k/20260820/20260821T125627Z"
    )
    ledger_path = (
        repository
        / "data/v2/universe/sec_edgar_8k/20260820/20260821T125627Z"
        / "universe_ledger.jsonl"
    )
    envelope_path = ledger_path.with_name("materialization.json")
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    segmented_root = _write_segmented_runtime_store(
        tmp_path / "checked-in-segmented-runtime", ledger_path
    )
    rotate_segmented_v2_universe_checkpoint(segmented_root)
    copied_source = tmp_path / "checked-in-copied-source"
    copied_envelope = tmp_path / "checked-in-copied-materialization.json"
    copied_segmented_root = tmp_path / "checked-in-copied-segmented-runtime"
    shutil.copytree(source_dir, copied_source)
    shutil.copy2(envelope_path, copied_envelope)
    shutil.copytree(segmented_root, copied_segmented_root)
    offset_as_of = (
        datetime.fromisoformat(
            envelope["universe_manifest"]["membership_as_of"].replace("Z", "+00:00")
        )
        .astimezone(ZoneInfo("America/Los_Angeles"))
        .isoformat()
    )
    request = {
        "manifest_id": envelope["universe_manifest"]["manifest_id"],
        "as_of": envelope["universe_manifest"]["membership_as_of"],
    }

    legacy = read_sec_8k_daily_runtime_universe(
        source_dir,
        envelope_path,
        backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
        storage_location=ledger_path,
        **request,
    )
    segmented = read_sec_8k_replay_runtime_universe(
        copied_source,
        copied_envelope,
        backend=LEDGER_BACKEND_SEGMENTED_HOT_V1,
        storage_location=copied_segmented_root,
        manifest_id=request["manifest_id"],
        as_of=offset_as_of,
    )

    assert segmented["membership_count"] == 111
    assert segmented["membership_snapshot"] == legacy["membership_snapshot"]
    assert segmented["membership_snapshot_sha256"] == legacy[
        "membership_snapshot_sha256"
    ]
    assert segmented["shared_reader_snapshot_hash"] == legacy[
        "shared_reader_snapshot_hash"
    ]
    assert segmented["trade_enabled"] is False


def test_runtime_adapter_rejects_unknown_backend_before_any_storage_read(
    tmp_path, monkeypatch
):
    def forbidden_read(*args, **kwargs):
        raise AssertionError("unsupported backend touched storage")

    monkeypatch.setattr(runtime_adapter_module, "_read_json", forbidden_read)
    with pytest.raises(V2SEC8KRuntimeAdapterError) as caught:
        read_sec_8k_runtime_universe(
            tmp_path / "source",
            tmp_path / "envelope.json",
            backend="auto",
            storage_location=tmp_path / "ledger",
            manifest_id="manifest-id",
            as_of=FROZEN_AT,
        )
    assert caught.value.code == "runtime_ledger_backend_unsupported"


def test_segmented_hot_runtime_propagates_checkpoint_damage_without_fallback(
    tmp_path, monkeypatch
):
    source_dir, ledger_path, envelope_path, manifest_id, as_of = (
        _published_runtime_fixture(tmp_path)
    )
    segmented_root = _write_segmented_runtime_store(
        tmp_path / "damaged-segmented-runtime", ledger_path
    )
    rotate_segmented_v2_universe_checkpoint(segmented_root)
    head = json.loads((segmented_root / "HEAD.json").read_text(encoding="utf-8"))
    segmented_record_path(
        segmented_root, "checkpoint", head["checkpoint_hash"]
    ).unlink()

    def forbidden_legacy(*args, **kwargs):
        raise AssertionError("segmented-hot damage fell back to legacy")

    monkeypatch.setattr(
        runtime_adapter_module,
        "validate_persisted_sec_8k_materialization",
        forbidden_legacy,
    )
    monkeypatch.setattr(
        runtime_adapter_module,
        "read_v2_universe_membership",
        forbidden_legacy,
    )
    monkeypatch.setattr(
        segments_module,
        "_load_exact_generations",
        forbidden_legacy,
    )
    with pytest.raises(V2SEC8KRuntimeAdapterError) as caught:
        read_sec_8k_runtime_universe(
            source_dir,
            envelope_path,
            backend=LEDGER_BACKEND_SEGMENTED_HOT_V1,
            storage_location=segmented_root,
            manifest_id=manifest_id,
            as_of=as_of,
        )
    assert caught.value.code == "segmented_checkpoint_missing"


def test_runtime_adapter_rejects_materialization_tamper(tmp_path):
    source_dir = _source_bundle(tmp_path)
    ledger_path = tmp_path / "runtime" / "universe.jsonl"
    envelope_path = tmp_path / "runtime" / "materialization.json"
    publish_sec_8k_materialization(source_dir, ledger_path, envelope_path)
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    manifest_id = envelope["universe_manifest"]["manifest_id"]
    as_of = envelope["universe_manifest"]["membership_as_of"]
    envelope["universe_manifest"]["manifest_hash"] = "0" * 64
    envelope_path.write_text(json.dumps(envelope, sort_keys=True), encoding="utf-8")

    with pytest.raises(V2SEC8KRuntimeAdapterError) as caught:
        read_sec_8k_runtime_universe(
            source_dir,
            envelope_path,
            backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
            storage_location=ledger_path,
            manifest_id=manifest_id,
            as_of=as_of,
        )
    assert caught.value.code == "runtime_materialization_hash_mismatch"


@pytest.mark.parametrize("payload", ['{"invalid":NaN}', '{"invalid":1e999}'])
def test_runtime_adapter_rejects_nonfinite_json_with_stable_error(tmp_path, payload):
    envelope_path = tmp_path / "materialization.json"
    envelope_path.write_text(payload, encoding="utf-8")

    with pytest.raises(V2SEC8KRuntimeAdapterError) as caught:
        read_sec_8k_runtime_universe(
            tmp_path / "source",
            envelope_path,
            backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
            storage_location=tmp_path / "universe.jsonl",
            manifest_id="manifest-id",
            as_of=FROZEN_AT,
        )
    assert caught.value.code == "runtime_materialization_unreadable"


@pytest.mark.parametrize(
    ("manifest_id", "as_of", "code"),
    [
        ("wrong-manifest", FROZEN_AT, "runtime_manifest_id_mismatch"),
        (None, "2026-08-21T12:30:00", "timezone_aware_instant_required"),
        (None, "2026-08-21T12:29:59Z", "as_of_before_ledger_population"),
        (None, "2026-08-21T12:30:01Z", "as_of_after_membership_projection"),
    ],
)
def test_runtime_adapter_requires_exact_manifest_and_causal_as_of(
    tmp_path, manifest_id, as_of, code
):
    source_dir = _source_bundle(tmp_path)
    ledger_path = tmp_path / "runtime" / "universe.jsonl"
    envelope_path = tmp_path / "runtime" / "materialization.json"
    publish_sec_8k_materialization(source_dir, ledger_path, envelope_path)
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))

    with pytest.raises(V2SEC8KRuntimeAdapterError) as caught:
        read_sec_8k_runtime_universe(
            source_dir,
            envelope_path,
            backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
            storage_location=ledger_path,
            manifest_id=manifest_id or envelope["universe_manifest"]["manifest_id"],
            as_of=as_of,
        )
    assert caught.value.code == code


def test_runtime_adapter_consumes_the_envelope_identity_it_validated(
    tmp_path, monkeypatch
):
    source_dir = _source_bundle(tmp_path)
    ledger_path = tmp_path / "runtime" / "universe.jsonl"
    envelope_path = tmp_path / "runtime" / "materialization.json"
    publish_sec_8k_materialization(source_dir, ledger_path, envelope_path)
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    real_validate = runtime_adapter_module.validate_persisted_sec_8k_materialization

    def validate_then_replace(*args, **kwargs):
        verified = real_validate(*args, **kwargs)
        envelope_path.write_text('{"unvalidated":"replacement"}', encoding="utf-8")
        return verified

    monkeypatch.setattr(
        runtime_adapter_module,
        "validate_persisted_sec_8k_materialization",
        validate_then_replace,
    )
    runtime = read_sec_8k_runtime_universe(
        source_dir,
        envelope_path,
        backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
        storage_location=ledger_path,
        manifest_id=envelope["universe_manifest"]["manifest_id"],
        as_of=envelope["universe_manifest"]["membership_as_of"],
    )
    assert runtime["input_identity"]["envelope_hash"] == envelope["envelope_hash"]
    assert runtime["boundary"]["trade_enabled"] is False


def test_runtime_adapter_rejects_boundary_escalation(tmp_path, monkeypatch):
    source_dir = _source_bundle(tmp_path)
    ledger_path = tmp_path / "runtime" / "universe.jsonl"
    envelope_path = tmp_path / "runtime" / "materialization.json"
    publish_sec_8k_materialization(source_dir, ledger_path, envelope_path)
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    envelope["boundary"]["paper_live_eligible"] = True
    payload = dict(envelope)
    payload.pop("envelope_hash")
    envelope["envelope_hash"] = canonical_hash(payload)

    def verified_without_rebuild(*args, **kwargs):
        return {
            "status": "verified",
            "manifest_id": envelope["universe_manifest"]["manifest_id"],
            "manifest_hash": envelope["universe_manifest"]["manifest_hash"],
            "coverage_snapshot_id": envelope["coverage_snapshot"]["coverage_snapshot_id"],
            "coverage_snapshot_hash": envelope["coverage_snapshot"]["record_hash"],
            "envelope_hash": envelope["envelope_hash"],
        }

    monkeypatch.setattr(
        "quant.v2_sec_8k_runtime_adapter.validate_persisted_sec_8k_materialization",
        verified_without_rebuild,
    )
    envelope_path.write_text(json.dumps(envelope, sort_keys=True), encoding="utf-8")

    with pytest.raises(V2SEC8KRuntimeAdapterError) as caught:
        read_sec_8k_runtime_universe(
            source_dir,
            envelope_path,
            backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
            storage_location=ledger_path,
            manifest_id=envelope["universe_manifest"]["manifest_id"],
            as_of=envelope["universe_manifest"]["membership_as_of"],
        )
    assert caught.value.code == "runtime_boundary_escalation_forbidden"


def test_pre_engine0_observation_uses_one_explicit_adapter_and_true_aliases(
    tmp_path, monkeypatch
):
    source_dir, ledger_path, envelope_path, manifest_id, as_of = (
        _published_runtime_fixture(tmp_path)
    )
    real_adapter = universe_observation_module.read_sec_8k_runtime_universe
    expected_runtime = _read_runtime_fixture(
        source_dir, ledger_path, envelope_path, manifest_id, as_of
    )
    calls = []

    def counted_adapter(*args, **kwargs):
        calls.append((args, kwargs))
        return real_adapter(*args, **kwargs)

    monkeypatch.setattr(
        universe_observation_module,
        "read_sec_8k_runtime_universe",
        counted_adapter,
    )
    observation = observe_sec_8k_universe(
        source_dir,
        envelope_path,
        backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
        storage_location=ledger_path,
        manifest_id=manifest_id,
        as_of=as_of,
    )

    assert len(calls) == 1
    assert calls[0][1] == {
        "backend": LEDGER_BACKEND_LEGACY_JSONL_V1,
        "storage_location": ledger_path,
        "manifest_id": manifest_id,
        "as_of": as_of,
    }
    assert observe_sec_8k_daily_universe is observe_sec_8k_universe
    assert observe_sec_8k_replay_universe is observe_sec_8k_universe
    assert observation["consumer_stage"] == "pre_engine0_universe_observation"
    assert observation["observation_scope"] == "source_bound_universe_membership_only"
    assert observation["engine0_policy_invoked"] is False
    assert observation["engine0_baseline_established"] is False
    assert observation["market_decision_clock_status"] == "unwired"
    assert observation["membership_count"] == 1
    assert observation["memberships"][0]["security_id"] == "sec-association-0000001001-aaa"
    assert (
        observation["memberships"]
        == expected_runtime["membership_snapshot"]["memberships"]
    )
    assert observation["memberships"][0]["state"] == "discovered"
    assert observation["input_identity"]["manifest_id"] == manifest_id
    assert observation["input_identity"]["as_of"] == "2026-08-21T12:30:00Z"
    assert observation["input_identity_sha256"] == canonical_hash(
        observation["input_identity"]
    )
    payload = dict(observation)
    supplied_hash = payload.pop("observation_snapshot_hash")
    assert supplied_hash == canonical_hash(payload)
    assert observation["outcome_blind"] is True
    assert observation["results_accessed"] is False
    assert observation["trade_enabled"] is False
    assert observation["boundary"]["paper_live_eligible"] is False
    assert observation["boundary"]["parity_status"] == "contract_only_unwired"
    forbidden_fields = {
        "candidate",
        "signal",
        "score",
        "rank",
        "decision",
        "order",
        "fill",
        "position",
    }
    assert forbidden_fields.isdisjoint(observation)
    assert all(forbidden_fields.isdisjoint(row) for row in observation["memberships"])


def test_pre_engine0_observation_forwards_segmented_hot_backend_once_per_alias(
    tmp_path, monkeypatch
):
    source_dir, ledger_path, envelope_path, manifest_id, as_of = (
        _published_runtime_fixture(tmp_path)
    )
    segmented_root = _write_segmented_runtime_store(
        tmp_path / "segmented-observation", ledger_path
    )
    rotate_segmented_v2_universe_checkpoint(segmented_root)
    copied_source = tmp_path / "copied-segmented-observation-source"
    copied_envelope = tmp_path / "copied-segmented-observation.json"
    copied_segmented_root = tmp_path / "copied-segmented-observation"
    shutil.copytree(source_dir, copied_source)
    shutil.copy2(envelope_path, copied_envelope)
    shutil.copytree(segmented_root, copied_segmented_root)
    real_adapter = universe_observation_module.read_sec_8k_runtime_universe
    calls = []
    runtime_snapshots = []

    def counted_adapter(*args, **kwargs):
        calls.append((args, kwargs))
        runtime = real_adapter(*args, **kwargs)
        runtime_snapshots.append(runtime)
        return runtime

    monkeypatch.setattr(
        universe_observation_module,
        "read_sec_8k_runtime_universe",
        counted_adapter,
    )
    observation = observe_sec_8k_daily_universe(
        source_dir,
        envelope_path,
        backend=LEDGER_BACKEND_SEGMENTED_HOT_V1,
        storage_location=segmented_root,
        manifest_id=manifest_id,
        as_of=as_of,
    )
    replay = observe_sec_8k_replay_universe(
        copied_source,
        copied_envelope,
        backend=LEDGER_BACKEND_SEGMENTED_HOT_V1,
        storage_location=copied_segmented_root,
        manifest_id=manifest_id,
        as_of="2026-08-21T05:30:00-07:00",
    )

    assert len(calls) == 2
    assert calls[0][0] == (source_dir, envelope_path)
    assert calls[0][1] == {
        "backend": LEDGER_BACKEND_SEGMENTED_HOT_V1,
        "storage_location": segmented_root,
        "manifest_id": manifest_id,
        "as_of": as_of,
    }
    assert calls[1][0] == (copied_source, copied_envelope)
    assert calls[1][1] == {
        "backend": LEDGER_BACKEND_SEGMENTED_HOT_V1,
        "storage_location": copied_segmented_root,
        "manifest_id": manifest_id,
        "as_of": "2026-08-21T05:30:00-07:00",
    }
    assert observe_sec_8k_daily_universe is observe_sec_8k_universe
    assert observe_sec_8k_replay_universe is observe_sec_8k_universe
    assert observation == replay
    assert observation["schema_version"] == 2
    assert (
        observation["observation_contract"]
        == "v2_pre_engine0_default_off_universe_observation_v2"
    )
    assert observation["ledger_backend"] == LEDGER_BACKEND_SEGMENTED_HOT_V1
    assert observation["input_identity"][
        "segmented_hot_state_identity_sha256"
    ] == runtime_snapshots[0]["input_identity"][
        "segmented_hot_state_identity_sha256"
    ]
    assert observation["input_identity"][
        "runtime_adapter_snapshot_hash"
    ] == runtime_snapshots[0]["adapter_snapshot_hash"]
    assert observation["input_identity"][
        "runtime_input_identity_sha256"
    ] == runtime_snapshots[0]["input_identity_sha256"]
    assert observation["memberships"] == runtime_snapshots[0]["membership_snapshot"][
        "memberships"
    ]
    assert observation["engine0_policy_invoked"] is False
    assert observation["trade_enabled"] is False


def test_pre_engine0_observation_is_path_and_offset_invariant(tmp_path):
    source_dir, ledger_path, envelope_path, manifest_id, as_of = (
        _published_runtime_fixture(tmp_path)
    )

    daily = observe_sec_8k_daily_universe(
        source_dir,
        envelope_path,
        backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
        storage_location=ledger_path,
        manifest_id=manifest_id,
        as_of=as_of,
    )
    copied_source = tmp_path / "copied-source"
    copied_runtime = tmp_path / "copied-runtime"
    shutil.copytree(source_dir, copied_source)
    shutil.copytree(ledger_path.parent, copied_runtime)
    replay = observe_sec_8k_replay_universe(
        copied_source,
        copied_runtime / envelope_path.name,
        backend=LEDGER_BACKEND_LEGACY_JSONL_V1,
        storage_location=copied_runtime / ledger_path.name,
        manifest_id=manifest_id,
        as_of="2026-08-21T05:30:00-07:00",
    )

    assert daily == replay
    assert (
        daily["observation_parity_status"]
        == "daily_replay_alias_verified_research_only"
    )


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("results_accessed", "observation_boundary_escalation_forbidden"),
        ("membership_count", "observation_membership_count_mismatch"),
        ("membership_trade_enabled", "observation_boundary_escalation_forbidden"),
        ("membership_pit_tier", "observation_boundary_escalation_forbidden"),
        ("membership_result_ceiling", "observation_boundary_escalation_forbidden"),
        ("membership_coverage", "observation_boundary_escalation_forbidden"),
        ("membership_parity", "observation_boundary_escalation_forbidden"),
        ("membership_paper_live", "observation_boundary_escalation_forbidden"),
        ("membership_authority", "observation_boundary_escalation_forbidden"),
    ],
)
def test_pre_engine0_observation_rejects_resealed_runtime_escalation(
    tmp_path, monkeypatch, mutation, code
):
    def mutate(runtime):
        if mutation == "results_accessed":
            runtime["results_accessed"] = True
        elif mutation == "membership_count":
            runtime["membership_count"] += 1
        else:
            field, value = {
                "membership_trade_enabled": ("trade_enabled", True),
                "membership_pit_tier": ("pit_tier", "canonical_pit"),
                "membership_result_ceiling": ("result_ceiling", "gate_eligible"),
                "membership_coverage": (
                    "external_universe_coverage_status",
                    "verified",
                ),
                "membership_parity": ("parity_status", "production_verified"),
                "membership_paper_live": ("paper_live_eligible", True),
                "membership_authority": ("authority", "paper"),
            }[mutation]
            runtime["membership_snapshot"][field] = value

    _assert_resealed_observation_rejected(
        tmp_path,
        monkeypatch,
        mutate,
        code=code,
        refresh_membership_semantics=True,
    )


def test_pre_engine0_observation_rejects_contradictory_runtime_identity(
    tmp_path, monkeypatch
):
    def mutate(runtime):
        runtime["input_identity"]["as_of"] = "2026-08-21T12:29:59Z"
        runtime["input_identity_sha256"] = canonical_hash(runtime["input_identity"])

    _assert_resealed_observation_rejected(
        tmp_path,
        monkeypatch,
        mutate,
        code="observation_runtime_identity_mismatch",
        refresh_membership_semantics=True,
    )


def test_pre_engine0_observation_rejects_missing_legacy_backend_identity_field(
    tmp_path, monkeypatch
):
    def mutate(runtime):
        del runtime["input_identity"]["segmented_hot_state_identity_sha256"]
        runtime["input_identity_sha256"] = canonical_hash(runtime["input_identity"])

    _assert_resealed_observation_rejected(
        tmp_path,
        monkeypatch,
        mutate,
        code="observation_runtime_backend_identity_mismatch",
        refresh_membership_semantics=False,
    )


def test_pre_engine0_observation_rejects_unhashable_backend_identity(
    tmp_path, monkeypatch
):
    def mutate(runtime):
        runtime["ledger_backend"] = []
        runtime["input_identity"]["ledger_backend"] = []
        runtime["input_identity_sha256"] = canonical_hash(runtime["input_identity"])

    _assert_resealed_observation_rejected(
        tmp_path,
        monkeypatch,
        mutate,
        code="observation_runtime_backend_identity_mismatch",
        refresh_membership_semantics=False,
    )


def test_pre_engine0_observation_rejects_injected_membership_fields(
    tmp_path, monkeypatch
):
    def mutate(runtime):
        runtime["membership_snapshot"]["memberships"][0]["rank"] = 1

    _assert_resealed_observation_rejected(
        tmp_path,
        monkeypatch,
        mutate,
        code="observation_membership_shape_invalid",
        refresh_membership_semantics=False,
    )


def test_pre_engine0_observation_rejects_resealed_membership_value_drift(
    tmp_path, monkeypatch
):
    def mutate(runtime):
        runtime["membership_snapshot"]["memberships"][0]["symbol"] = "TAMPERED"

    _assert_resealed_observation_rejected(
        tmp_path,
        monkeypatch,
        mutate,
        code="observation_membership_identity_mismatch",
        refresh_membership_semantics=False,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mapping_sha256", "x" * 64),
        ("state", "scored"),
        ("effective_at", "2026-08-21T12:30:00"),
    ],
)
def test_pre_engine0_observation_rejects_resealed_membership_scalar_drift(
    tmp_path, monkeypatch, field, value
):
    def mutate(runtime):
        runtime["membership_snapshot"]["memberships"][0][field] = value

    _assert_resealed_observation_rejected(
        tmp_path,
        monkeypatch,
        mutate,
        code="observation_membership_shape_invalid",
        refresh_membership_semantics=True,
    )


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("out_of_order", "observation_membership_order_invalid"),
        ("duplicate", "observation_membership_identity_duplicate"),
    ],
)
def test_pre_engine0_observation_rejects_resealed_membership_population_drift(
    tmp_path, monkeypatch, mutation, code
):
    def mutate(runtime):
        membership = runtime["membership_snapshot"]
        original = membership["memberships"][0]
        if mutation == "out_of_order":
            later_identity = dict(original)
            later_identity["security_id"] = "zz-security"
            later_identity["listing_id"] = "zz-listing"
            membership["memberships"] = [later_identity, original]
        else:
            membership["memberships"].append(dict(original))
        runtime["membership_count"] = 2

    _assert_resealed_observation_rejected(
        tmp_path,
        monkeypatch,
        mutate,
        code=code,
        refresh_membership_semantics=True,
    )


def test_publish_refuses_to_overwrite_an_existing_envelope(tmp_path):
    source_dir = _source_bundle(tmp_path)
    ledger_path = tmp_path / "published" / "universe.jsonl"
    envelope_path = tmp_path / "published" / "materialization.json"
    envelope_path.parent.mkdir(parents=True)
    original = b'{"preexisting":"immutable"}\n'
    envelope_path.write_bytes(original)

    with pytest.raises(V2SEC8KUniverseError) as caught:
        publish_sec_8k_materialization(source_dir, ledger_path, envelope_path)
    assert "conflict" in caught.value.code
    assert envelope_path.read_bytes() == original


def test_publish_rejects_ledger_envelope_path_collision_before_writing(tmp_path):
    source_dir = _source_bundle(tmp_path)
    shared_path = tmp_path / "collision" / "shared.json"

    with pytest.raises(V2SEC8KUniverseError) as caught:
        publish_sec_8k_materialization(source_dir, shared_path, shared_path)

    assert caught.value.code == "persistence_path_collision"
    assert not shared_path.exists()


def test_concurrent_bundle_publishers_commit_one_manifest_without_overwrite(tmp_path):
    source_dir = _source_bundle(tmp_path)
    (source_dir / "bundle.json").unlink()
    alternate_metadata = json.loads(json.dumps(RETRIEVAL_METADATA))
    for item in alternate_metadata.values():
        item["request_headers"]["User-Agent"] = "ginger-v2-alt alt@example.com"
    start = Barrier(2)

    def create(metadata):
        start.wait()
        try:
            manifest = create_source_bundle_manifest(
                source_dir,
                FORM_DATE,
                ARTIFACT_TIMES,
                FROZEN_AT,
                retrieval_metadata_by_artifact=metadata,
            )
            return "committed", manifest["bundle_sha256"]
        except V2SEC8KUniverseError as exc:
            return "rejected", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, (RETRIEVAL_METADATA, alternate_metadata)))

    assert sorted(item[0] for item in results) == ["committed", "rejected"]
    assert "conflict" in next(item[1] for item in results if item[0] == "rejected")
    assert build_sec_8k_materialization(source_dir)["input_bundle_sha256"] == next(
        item[1] for item in results if item[0] == "committed"
    )


def test_concurrent_different_publishers_commit_one_envelope_without_overwrite(
    tmp_path,
):
    first_source = _source_bundle(tmp_path)
    second_source = tmp_path / "second-source"
    shutil.copytree(first_source, second_source)
    _replace_mapping_surface(
        second_source,
        [
            [1001, "Alpha Incorporated", "AAX", "Nasdaq"],
            [1003, "Ambiguous Association Corp", "AMB", "Nasdaq"],
            [1003, "Ambiguous Association Corp Class B", "AM.B", "NYSE"],
            [1004, "Unsupported Venue Corp", "OTCX", "OTC"],
            [1005, "Amended Filing Is Out Of Scope", "AMD", "Nasdaq"],
        ],
    )
    ledger_path = tmp_path / "concurrent" / "universe.jsonl"
    envelope_path = tmp_path / "concurrent" / "materialization.json"
    start = Barrier(2)

    def publish(index_and_source):
        index, source_dir = index_and_source
        start.wait()
        try:
            return index, "committed", publish_sec_8k_materialization(
                source_dir, ledger_path, envelope_path
            )
        except V2SEC8KUniverseError as exc:
            return index, "rejected", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, enumerate((first_source, second_source))))

    assert sorted(item[1] for item in results) == ["committed", "rejected"]
    rejected = next(item for item in results if item[1] == "rejected")
    assert "conflict" in rejected[2]
    committed = next(item for item in results if item[1] == "committed")
    winning_source = (first_source, second_source)[committed[0]]
    validate_persisted_sec_8k_materialization(
        winning_source, ledger_path, envelope_path
    )


def test_retry_heals_after_ledger_commit_and_envelope_write_failure(
    tmp_path, monkeypatch
):
    source_dir = _source_bundle(tmp_path)
    ledger_path = tmp_path / "published" / "universe.jsonl"
    envelope_path = tmp_path / "published" / "materialization.json"
    real_atomic_write_json = sec_8k_module.atomic_write_json
    failed = False

    def fail_envelope_once(obj, filepath, **kwargs):
        nonlocal failed
        if Path(filepath) == envelope_path and not failed:
            failed = True
            raise OSError("synthetic envelope write failure")
        return real_atomic_write_json(obj, filepath, **kwargs)

    monkeypatch.setattr(sec_8k_module, "atomic_write_json", fail_envelope_once)
    with pytest.raises(OSError, match="synthetic envelope write failure"):
        publish_sec_8k_materialization(source_dir, ledger_path, envelope_path)

    assert ledger_path.exists()
    assert not envelope_path.exists()
    retried = publish_sec_8k_materialization(source_dir, ledger_path, envelope_path)
    assert retried["status"] == "committed"
    assert retried["ledger_status"] == "duplicate"
    assert retried["envelope_status"] == "committed"
    validate_persisted_sec_8k_materialization(source_dir, ledger_path, envelope_path)
