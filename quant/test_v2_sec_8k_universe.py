from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
from threading import Barrier

import pytest

import quant.v2_sec_8k_universe as sec_8k_module
from quant.v2_sec_8k_universe import (
    V2SEC8KUniverseError,
    build_sec_8k_materialization,
    create_source_bundle_manifest,
    freeze_sec_8k_source_bundle,
    publish_sec_8k_materialization,
    validate_persisted_sec_8k_materialization,
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
