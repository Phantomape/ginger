from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent))

from usaspending_obligation_observer import (  # noqa: E402
    DOWNLOAD_TRANSACTIONS_URL,
    ELIGIBILITY_RULE,
    HISTORICAL_PIT_STATUS,
    PENDING_JOB_JOURNAL_NAME,
    PRODUCER_MODE,
    build_daily_transaction_download_request,
    fetch_daily_transaction_snapshot,
    main,
    parse_usaspending_transaction_snapshot,
    persist_daily_usaspending_obligation_observer,
    persist_producer_health_summary,
    persist_usaspending_obligation_observer,
    run_observer,
)


CANONICAL_HEADER = [
    "contract_transaction_unique_key",
    "award_id_piid",
    "modification_number",
    "action_date",
    "initial_report_date",
    "last_modified_date",
    "federal_action_obligation",
    "base_and_all_options_value",
    "base_and_exercised_options_value",
    "current_total_value_of_award",
    "potential_total_value_of_award",
    "recipient_name",
    "recipient_uei",
    "recipient_parent_name",
    "recipient_parent_uei",
    "awarding_agency_name",
    "awarding_sub_agency_name",
    "awarding_office_name",
    "naics_code",
    "naics_description",
    "transaction_description",
    "action_type_code",
    "action_type",
]


def _row(
    key: str,
    *,
    obligation: str = "100.00",
    ceiling: str = "0.00",
    agency: str = "National Aeronautics and Space Administration",
    sub_agency: str = "",
    recipient: str = "PUBLIC COMPANY INC.",
    initial_report_date: str = "2026-07-10 18:00:00+00",
) -> list[str]:
    return [
        key,
        f"AWARD-{key}",
        "P00001",
        "2026-07-10",
        initial_report_date,
        "2026-07-10 19:00:00+00",
        obligation,
        ceiling,
        ceiling,
        "1000.00",
        "2000.00",
        recipient,
        "UEI123",
        "PUBLIC PARENT CORPORATION",
        "PARENTUEI123",
        agency,
        sub_agency,
        "OFFICE",
        "541715",
        "R&D",
        "TEST TRANSACTION",
        "C",
        "FUNDING ONLY ACTION",
    ]


def _write_csv(path: Path, rows: list[list[str]], header: list[str] | None = None) -> Path:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header or CANONICAL_HEADER)
        writer.writerows(rows)
    return path


def _write_zip(path: Path, rows: list[list[str]]) -> Path:
    path.write_bytes(_zip_bytes(rows))
    return path


def _zip_bytes(
    rows: list[list[str]],
    *,
    member_name: str = "Contracts_PrimeTransactions_1.csv",
    header: list[str] | None = None,
) -> bytes:
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(header or CANONICAL_HEADER)
    writer.writerows(rows)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Contracts_Subawards.csv", "ignored\n")
        archive.writestr(
            member_name,
            text.getvalue().encode("utf-8-sig"),
        )
    return output.getvalue()


def _ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class _FakeProducerHttp:
    def __init__(
        self,
        *,
        zip_payload: bytes,
        statuses: list[dict] | None = None,
        initial_overrides: dict | None = None,
    ) -> None:
        self.status_url = (
            "https://api.usaspending.gov/api/v2/download/status?file=test.zip"
        )
        self.file_url = "https://files.usaspending.gov/generated_downloads/test.zip"
        self.zip_payload = zip_payload
        self.statuses = list(statuses or [{"status": "finished"}])
        self.initial_overrides = dict(initial_overrides or {})
        self.post_calls: list[tuple[str, dict, float]] = []
        self.get_calls: list[tuple[str, float]] = []

    def post(self, url: str, payload: dict, *, timeout: float):
        self.post_calls.append((url, payload, timeout))
        return {
            "status_url": self.status_url,
            "file_name": "test.zip",
            "file_url": self.file_url,
            **self.initial_overrides,
        }

    def get(self, url: str, *, timeout: float):
        self.get_calls.append((url, timeout))
        if url == self.status_url:
            if not self.statuses:
                raise AssertionError("unexpected extra status poll")
            return self.statuses.pop(0)
        if url == self.file_url:
            return self.zip_payload
        raise AssertionError(f"unexpected GET URL: {url}")


def _clock(*timestamps: str):
    values = iter(
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        for value in timestamps
    )
    return lambda: next(values)


def test_schema_aliases_parse_official_search_style_columns(tmp_path: Path):
    header = [
        "Contract Transaction Unique Key",
        "Award ID",
        "Mod",
        "Action Date",
        "Initial Report Date",
        "Last Modified Date",
        "Transaction Amount",
        "Base And All Options Value",
        "Recipient Name",
        "Recipient UEI",
        "Recipient Parent Name",
        "Recipient Parent UEI",
        "Awarding Agency",
        "Awarding Sub Agency",
        "NAICS Code",
        "Description",
    ]
    row = [
        "TX-ALIAS",
        "ABC123",
        "P00001",
        "2026-07-10",
        "2026-07-10 18:00:00+00",
        "2026-07-10 19:00:00+00",
        "$1,250.00",
        "0",
        "PUBLIC COMPANY INC.",
        "UEI123",
        "PUBLIC PARENT CORPORATION",
        "PARENTUEI123",
        "National Aeronautics and Space Administration",
        "NASA",
        "541715",
        "R&D SERVICES",
    ]
    source = _write_csv(tmp_path / "alias.csv", [row], header)

    parsed = parse_usaspending_transaction_snapshot(source)

    assert len(parsed) == 1
    assert parsed[0]["transaction_key"] == "TX-ALIAS"
    assert parsed[0]["federal_action_obligation"] == 1250.0
    assert parsed[0]["base_and_all_options_value"] == 0.0
    assert parsed[0]["recipient_parent_name"] == "PUBLIC PARENT CORPORATION"
    assert parsed[0]["recipient_parent_uei"] == "PARENTUEI123"
    assert parsed[0]["eligible"] is True
    assert parsed[0]["eligibility_rule"] == ELIGIBILITY_RULE


def test_eligibility_is_positive_obligation_without_ceiling_expansion(tmp_path: Path):
    source = _write_csv(
        tmp_path / "eligibility.csv",
        [
            _row("ELIGIBLE-ZERO", obligation="10", ceiling="0"),
            _row("ELIGIBLE-NEG", obligation="10", ceiling="-5"),
            _row("NO-ZERO-OBL", obligation="0", ceiling="0"),
            _row("NO-DEOBL", obligation="-10", ceiling="0"),
            _row("NO-CEILING", obligation="10", ceiling="1"),
            _row("NO-MISSING", obligation="", ceiling="0"),
        ],
    )

    parsed = {row["transaction_key"]: row for row in parse_usaspending_transaction_snapshot(source)}

    assert parsed["ELIGIBLE-ZERO"]["eligible"] is True
    assert parsed["ELIGIBLE-NEG"]["eligible"] is True
    assert parsed["NO-ZERO-OBL"]["eligibility_reason"] == "nonpositive_federal_action_obligation"
    assert parsed["NO-DEOBL"]["eligible"] is False
    assert parsed["NO-CEILING"]["eligibility_reason"] == "positive_ceiling_expansion"
    assert parsed["NO-MISSING"]["eligibility_reason"].startswith("missing_or_invalid")


def test_dod_and_usace_rows_are_seen_but_never_persisted(tmp_path: Path):
    source = _write_csv(
        tmp_path / "embargo.csv",
        [
            _row("NASA"),
            _row("DOD", agency="Department of Defense"),
            _row(
                "USACE",
                agency="Department of the Army",
                sub_agency="U.S. Army Corps of Engineers",
            ),
        ],
    )
    output = tmp_path / "observer"

    summary = persist_usaspending_obligation_observer(
        source,
        observed_at="2026-07-13T20:00:00Z",
        output_root=output,
    )

    rows = _ledger(output / "ledger.jsonl")
    state = json.loads((output / "state.json").read_text(encoding="utf-8"))
    assert [row["transaction_key"] for row in rows] == ["NASA"]
    assert summary["embargo_excluded_count"] == 2
    assert summary["embargo_excluded_counts"] == {
        "dod_90_day_publication_embargo": 1,
        "usace_90_day_publication_embargo": 1,
    }
    assert state["seen_transactions"]["DOD"]["embargo_excluded"] is True
    assert state["seen_transactions"]["USACE"]["embargo_excluded"] is True


def test_seed_rerun_and_later_zip_append_only_first_seen_delta(tmp_path: Path):
    first_source = _write_csv(
        tmp_path / "first.csv",
        [
            _row("A", obligation="100", ceiling="0"),
            _row("B", obligation="100", ceiling="50"),
        ],
    )
    output = tmp_path / "observer"

    first = persist_usaspending_obligation_observer(
        first_source,
        observed_at="2026-07-13T20:00:00Z",
        output_root=output,
    )
    first_ledger_bytes = (output / "ledger.jsonl").read_bytes()
    rerun = persist_daily_usaspending_obligation_observer(
        first_source,
        observed_at="2026-07-13T20:00:00Z",
        output_root=output,
    )

    assert first["bootstrap_snapshot"] is True
    assert first["historical_seed_rows_appended"] == 2
    assert first["new_forward_rows_appended"] == 0
    assert rerun["rows_appended"] == 0
    assert (output / "ledger.jsonl").read_bytes() == first_ledger_bytes
    seed_rows = _ledger(output / "ledger.jsonl")
    assert all(row["seed_not_forward"] is True for row in seed_rows)
    assert all(row["forward_event"] is False for row in seed_rows)
    assert all(row["candidate_eligible"] is False for row in seed_rows)
    assert all(row["candidate_eligibility_status"] == "seed_not_forward" for row in seed_rows)
    assert all(row["entry_date"] is None and row["target_price"] is None for row in seed_rows)
    assert all(row["observer_only"] is True and row["trade_enabled"] is False for row in seed_rows)
    assert all(row["historical_pit_status"] == HISTORICAL_PIT_STATUS for row in seed_rows)
    assert all(row["source_snapshot_sha256"] == first["source_snapshot_sha256"] for row in seed_rows)

    second_source = _write_zip(
        tmp_path / "second.zip",
        [
            _row("A", obligation="100", ceiling="0"),
            _row("B", obligation="100", ceiling="50"),
            _row(
                "C",
                obligation="250",
                ceiling="0",
                initial_report_date="2026-07-14 18:00:00+00",
            ),
            _row(
                "D",
                obligation="250",
                ceiling="25",
                initial_report_date="2026-07-14 18:00:00+00",
            ),
            _row(
                "DOD-NEW",
                agency="Department of Defense",
                initial_report_date="2026-07-14 18:00:00+00",
            ),
        ],
    )
    second = persist_usaspending_obligation_observer(
        second_source,
        observed_at="2026-07-14T20:00:00Z",
        output_root=output,
    )
    second_ledger_bytes = (output / "ledger.jsonl").read_bytes()
    second_rerun = persist_usaspending_obligation_observer(
        second_source,
        observed_at="2026-07-14T21:00:00Z",
        output_root=output,
    )

    assert second["new_forward_rows_appended"] == 2
    assert second["new_eligible_forward_rows_appended"] == 1
    assert second["embargo_excluded_count"] == 1
    assert second["ledger_row_count"] == 4
    assert second_rerun["rows_appended"] == 0
    assert second_rerun["embargo_excluded_count"] == 1
    assert second_rerun["new_embargo_excluded_count"] == 0
    assert (output / "ledger.jsonl").read_bytes() == second_ledger_bytes
    rows = _ledger(output / "ledger.jsonl")
    c_row = next(row for row in rows if row["transaction_key"] == "C")
    d_row = next(row for row in rows if row["transaction_key"] == "D")
    assert c_row["forward_event"] is True
    assert c_row["prospective_local_first_seen"] is True
    assert c_row["row_type"] == "prospective_local_first_seen"
    assert (
        c_row["forward_event_semantics"]
        == "prospective_local_first_seen_not_proof_of_first_publication"
    )
    assert c_row["does_not_prove_first_publication"] is True
    assert c_row["prospective_evidence_eligible"] is True
    assert c_row["source_freshness_guard_passed"] is True
    assert c_row["source_initial_report_date_utc"] == "2026-07-14"
    assert c_row["availability_timestamp_field"] == "first_seen_at"
    assert c_row["initial_report_date_freshness_role"].startswith(
        "eligibility_guard_only"
    )
    assert c_row["candidate_eligible"] is False
    assert c_row["candidate_eligibility_status"] == "blocked_no_audited_ticker_mapping"
    assert c_row["candidate_tickers"] == [] and c_row["ticker"] is None
    assert c_row["first_seen_at"] == "2026-07-14T20:00:00Z"
    assert d_row["forward_event"] is True
    assert d_row["prospective_evidence_eligible"] is False
    assert d_row["candidate_eligible"] is False
    assert d_row["candidate_eligibility_status"] == "ineligible_obligation_conversion_rule"
    assert all(row["entry_date"] is None and row["target_price"] is None for row in rows)
    assert not list(output.glob("*.tmp"))


def test_observation_clock_regression_fails_closed_without_writes(tmp_path: Path):
    first_source = _write_csv(tmp_path / "first.csv", [_row("A")])
    second_source = _write_csv(
        tmp_path / "second.csv",
        [
            _row("A"),
            _row(
                "NEW",
                initial_report_date="2026-07-14 18:00:00+00",
            ),
        ],
    )
    output = tmp_path / "observer"
    persist_usaspending_obligation_observer(
        first_source,
        observed_at="2026-07-14T20:00:00Z",
        output_root=output,
    )
    paths = [
        output / "state.json",
        output / "ledger.jsonl",
        output / "latest_summary.json",
    ]
    before = {path: path.read_bytes() for path in paths}

    with pytest.raises(ValueError, match="precedes prior observer clock"):
        persist_usaspending_obligation_observer(
            second_source,
            observed_at="2026-07-14T19:59:59Z",
            output_root=output,
        )

    assert {path: path.read_bytes() for path in paths} == before


def test_old_source_record_is_local_first_seen_but_not_evidence_eligible(
    tmp_path: Path,
):
    first_source = _write_csv(tmp_path / "first.csv", [_row("SEED")])
    output = tmp_path / "observer"
    persist_usaspending_obligation_observer(
        first_source,
        observed_at="2026-07-13T20:00:00Z",
        output_root=output,
    )
    second_source = _write_csv(
        tmp_path / "second.csv",
        [
            _row("SEED"),
            _row(
                "STALE",
                obligation="250",
                ceiling="0",
                initial_report_date="2026-07-12 23:59:59+00",
            ),
            _row(
                "FRESH",
                obligation="250",
                ceiling="0",
                initial_report_date="2026-07-13 00:00:00+00",
            ),
        ],
    )

    summary = persist_usaspending_obligation_observer(
        second_source,
        observed_at="2026-07-14T20:00:00Z",
        output_root=output,
    )

    rows = {row["transaction_key"]: row for row in _ledger(output / "ledger.jsonl")}
    stale = rows["STALE"]
    fresh = rows["FRESH"]
    assert stale["forward_event"] is True
    assert stale["prospective_local_first_seen"] is True
    assert stale["first_seen_at"] == "2026-07-14T20:00:00Z"
    assert stale["source_freshness_guard_passed"] is False
    assert (
        stale["source_freshness_status"]
        == "initial_report_date_precedes_observer_initialization"
    )
    assert stale["prospective_evidence_eligible"] is False
    assert stale["candidate_eligibility_status"] == "blocked_source_freshness_guard"
    assert stale["candidate_eligible"] is False
    assert stale["trade_enabled"] is False
    assert fresh["source_freshness_guard_passed"] is True
    assert fresh["prospective_evidence_eligible"] is True
    assert fresh["candidate_eligible"] is False
    assert fresh["trade_enabled"] is False
    assert summary["new_forward_rows_appended"] == 2
    assert summary["new_eligible_forward_rows_appended"] == 1
    assert summary["new_source_freshness_blocked_forward_rows_appended"] == 1
    assert summary["first_seen_scope"] == "local_observer_state"
    assert summary["does_not_prove_first_publication"] is True


def test_cli_main_persists_summary(tmp_path: Path, capsys):
    source = _write_csv(tmp_path / "cli.csv", [_row("CLI")])
    output = tmp_path / "cli-observer"

    result = main(
        [
            str(source),
            "--observed-at",
            "2026-07-13T20:00:00Z",
            "--output-root",
            str(output),
        ]
    )

    assert result == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["historical_seed_rows_appended"] == 1
    assert (output / "latest_summary.json").exists()


def test_run_observer_accepts_explicit_output_paths(tmp_path: Path):
    source = _write_csv(tmp_path / "run.csv", [_row("RUN")])
    state = tmp_path / "custom" / "state.json"
    ledger = tmp_path / "custom" / "ledger.jsonl"
    summary_path = tmp_path / "custom" / "summary.json"

    summary = run_observer(
        source,
        observed_at="2026-07-13T20:00:00Z",
        state_path=state,
        ledger_path=ledger,
        summary_path=summary_path,
    )

    assert summary["historical_seed_rows_appended"] == 1
    assert state.exists() and ledger.exists() and summary_path.exists()


def test_daily_producer_posts_fixed_request_polls_and_freezes_manifest(
    tmp_path: Path,
):
    http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A"), _row("B")]),
        statuses=[
            {"status": "ready"},
            {"status": "running"},
            {"status": "finished"},
        ],
    )
    sleeps: list[float] = []
    output = tmp_path / "observer"

    result = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=http.post,
        http_get=http.get,
        sleep_fn=sleeps.append,
        now_fn=_clock("2026-07-27T12:00:00Z", "2026-07-27T12:00:05Z"),
    )

    expected_request = build_daily_transaction_download_request("2026-07-27")
    assert result["status"] == "ok"
    assert result["producer_mode"] == PRODUCER_MODE
    assert result["source_mode"] == "official_producer"
    assert result["retrieved_at_utc"] == "2026-07-27T12:00:05Z"
    assert result["row_count"] == 2
    assert result["snapshot_reused"] is False
    assert sleeps == [2.0, 2.0]
    assert http.post_calls == [
        (DOWNLOAD_TRANSACTIONS_URL, expected_request, 30.0)
    ]
    assert [url for url, _ in http.get_calls] == [
        http.status_url,
        http.status_url,
        http.status_url,
        http.file_url,
    ]
    assert expected_request == {
        "filters": {
            "award_type_codes": ["A", "B", "C", "D"],
            "time_period": [
                {
                    "start_date": "2026-07-25",
                    "end_date": "2026-07-27",
                    "date_type": "last_modified_date",
                }
            ],
        },
        "columns": [],
        "file_format": "csv",
        "limit": 5000,
    }
    snapshot_path = Path(result["snapshot_path"])
    manifest_path = Path(result["manifest_path"])
    assert snapshot_path.is_file() and manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["download_request"] == expected_request
    assert manifest["requested_at_utc"] == "2026-07-27T12:00:00Z"
    assert manifest["retrieved_at_utc"] == "2026-07-27T12:00:05Z"
    assert manifest["job_status"] == "finished"
    assert manifest["row_count"] == 2
    assert manifest["raw_file_size_bytes"] == snapshot_path.stat().st_size
    assert manifest["raw_file_sha256"] == result["snapshot_sha256"]
    assert sorted(manifest["parser_required_columns"]) == [
        "awarding_agency_name",
        "base_and_all_options_value",
        "federal_action_obligation",
        "transaction_key",
    ]
    assert not list((output / "raw").glob("*.tmp"))


def test_daily_producer_same_run_date_reuses_validated_snapshot_without_http(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    http = _FakeProducerHttp(zip_payload=_zip_bytes([_row("A")]))
    first = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=http.post,
        http_get=http.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:00:00Z", "2026-07-27T12:00:01Z"),
    )
    snapshot_before = Path(first["snapshot_path"]).read_bytes()
    manifest_before = Path(first["manifest_path"]).read_bytes()
    journal_path = output / PENDING_JOB_JOURNAL_NAME
    journal_before = journal_path.read_bytes()
    assert json.loads(journal_before)["state"] == "completed"

    def unexpected_http(*_args, **_kwargs):
        raise AssertionError("idempotent reuse must not call HTTP")

    second = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=unexpected_http,
        http_get=unexpected_http,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T13:00:00Z"),
    )

    assert second["status"] == "ok"
    assert second["snapshot_reused"] is True
    assert second["retrieved_at_utc"] == first["retrieved_at_utc"]
    assert second["snapshot_sha256"] == first["snapshot_sha256"]
    assert second["manifest_sha256"] == first["manifest_sha256"]
    assert Path(first["snapshot_path"]).read_bytes() == snapshot_before
    assert Path(first["manifest_path"]).read_bytes() == manifest_before
    assert journal_path.read_bytes() == journal_before


def test_daily_producer_bounds_pending_status_without_download(tmp_path: Path):
    http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "ready"}, {"status": "running"}],
    )
    sleeps: list[float] = []

    result = fetch_daily_transaction_snapshot(
        "2026-07-27",
        tmp_path / "observer",
        http_post=http.post,
        http_get=http.get,
        sleep_fn=sleeps.append,
        now_fn=_clock("2026-07-27T12:00:00Z"),
        max_status_polls=2,
    )

    assert result["status"] == "pending"
    assert result["job_status"] == "running"
    assert result["status_poll_count"] == 2
    assert result["attempt_poll_count"] == 2
    assert result["status_history"] == ["ready", "running"]
    assert result["status_url"] == http.status_url
    assert result["file_name"] == "test.zip"
    assert result["file_url"] == http.file_url
    assert result["pending_job_validation_status"] == "validated"
    assert result["pending_job"]["download_request"] == (
        build_daily_transaction_download_request("2026-07-27")
    )
    assert result["snapshot_path"] is None
    assert result["manifest_path"] is None
    assert sleeps == [2.0]
    assert [url for url, _ in http.get_calls] == [http.status_url, http.status_url]


def test_daily_producer_resumes_persisted_pending_job_before_new_post(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    first_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "ready"}, {"status": "running"}],
    )
    first = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=first_http.post,
        http_get=first_http.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:00:00Z"),
        max_status_polls=2,
    )
    health = persist_producer_health_summary(
        run_date="2026-07-27",
        producer_result=first,
        output_dir=output,
    )
    assert health["status"] == "pending"
    assert health["producer_health"]["pending_job"] == first["pending_job"]
    assert health["pending_job_validation_status"] == "validated"

    post_calls: list[str] = []

    def unexpected_post(*_args, **_kwargs):
        post_calls.append("post")
        return {}

    resumed_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "finished"}],
    )
    resumed = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=unexpected_post,
        http_get=resumed_http.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:05:00Z", "2026-07-27T12:05:01Z"),
    )

    assert resumed["status"] == "ok"
    assert resumed["resumed_pending_job"] is True
    assert resumed["requested_at_utc"] == "2026-07-27T12:00:00Z"
    assert resumed["attempted_at_utc"] == "2026-07-27T12:05:00Z"
    assert resumed["status_history"] == ["ready", "running", "finished"]
    assert resumed["status_poll_count"] == 3
    assert resumed["attempt_poll_count"] == 1
    assert post_calls == []
    assert [url for url, _ in resumed_http.get_calls] == [
        resumed_http.status_url,
        resumed_http.file_url,
    ]
    manifest = json.loads(Path(resumed["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["requested_at_utc"] == "2026-07-27T12:00:00Z"
    assert manifest["attempted_at_utc"] == "2026-07-27T12:05:00Z"
    assert manifest["resumed_pending_job"] is True
    assert manifest["status_history"] == ["ready", "running", "finished"]
    observer = persist_usaspending_obligation_observer(
        resumed["snapshot_path"],
        observed_at=resumed["retrieved_at_utc"],
        output_root=output,
    )
    completed_health = persist_producer_health_summary(
        run_date="2026-07-27",
        producer_result=resumed,
        observer_summary=observer,
        output_dir=output,
    )
    assert completed_health["status"] == "ok"
    assert completed_health["resumed_pending_job"] is True
    assert completed_health["heartbeat_status"] == "fresh_success_zero_forward"


def test_daily_producer_cross_date_pending_job_blocks_duplicate_post(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    first_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "running"}],
    )
    first = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=first_http.post,
        http_get=first_http.get,
        now_fn=_clock("2026-07-27T23:55:00Z"),
        max_status_polls=1,
    )
    assert first["status"] == "pending"

    post_calls: list[str] = []

    def unexpected_post(*_args, **_kwargs):
        post_calls.append("post")
        return {}

    resumed_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "running"}],
    )
    resumed = fetch_daily_transaction_snapshot(
        "2026-07-28",
        output,
        http_post=unexpected_post,
        http_get=resumed_http.get,
        now_fn=_clock("2026-07-28T00:05:00Z"),
        max_status_polls=1,
    )

    assert resumed["status"] == "pending"
    assert resumed["run_date"] == "2026-07-27"
    assert resumed["download_request"] == build_daily_transaction_download_request(
        "2026-07-27"
    )
    assert resumed["resumed_pending_job"] is True
    assert resumed["attempt_poll_count"] == 1
    assert post_calls == []
    assert [url for url, _ in resumed_http.get_calls] == [
        resumed_http.status_url
    ]


def test_daily_producer_cross_date_finished_job_keeps_original_snapshot_date(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    first_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "running"}],
    )
    fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=first_http.post,
        http_get=first_http.get,
        now_fn=_clock("2026-07-27T23:55:00Z"),
        max_status_polls=1,
    )

    post_calls: list[str] = []

    def unexpected_post(*_args, **_kwargs):
        post_calls.append("post")
        return {}

    resumed_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "finished"}],
    )
    resumed = fetch_daily_transaction_snapshot(
        "2026-07-28",
        output,
        http_post=unexpected_post,
        http_get=resumed_http.get,
        now_fn=_clock("2026-07-28T00:05:00Z", "2026-07-28T00:05:01Z"),
    )

    assert resumed["status"] == "ok"
    assert resumed["run_date"] == "2026-07-27"
    assert resumed["resumed_pending_job"] is True
    assert post_calls == []
    assert Path(resumed["snapshot_path"]).name == "transaction_snapshot_20260727.zip"
    manifest = json.loads(Path(resumed["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["run_date"] == "2026-07-27"
    assert manifest["download_request"] == build_daily_transaction_download_request(
        "2026-07-27"
    )
    journal = json.loads(
        (output / PENDING_JOB_JOURNAL_NAME).read_text(encoding="utf-8")
    )
    assert journal["state"] == "completed"
    assert journal["run_date"] == "2026-07-27"
    assert journal["completion"]["snapshot_sha256"] == resumed["snapshot_sha256"]


def test_daily_producer_completed_cross_date_journal_is_ignored_on_next_call(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    first_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "running"}],
    )
    fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=first_http.post,
        http_get=first_http.get,
        now_fn=_clock("2026-07-27T23:55:00Z"),
        max_status_polls=1,
    )
    resumed_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "finished"}],
    )
    recovered = fetch_daily_transaction_snapshot(
        "2026-07-28",
        output,
        http_post=lambda *_args, **_kwargs: pytest.fail("must resume old job"),
        http_get=resumed_http.get,
        now_fn=_clock("2026-07-28T00:05:00Z", "2026-07-28T00:05:01Z"),
    )
    assert recovered["run_date"] == "2026-07-27"

    current_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("B")]),
        statuses=[{"status": "finished"}],
    )
    current = fetch_daily_transaction_snapshot(
        "2026-07-28",
        output,
        http_post=current_http.post,
        http_get=current_http.get,
        now_fn=_clock("2026-07-28T00:10:00Z", "2026-07-28T00:10:01Z"),
    )

    assert current["status"] == "ok"
    assert current["run_date"] == "2026-07-28"
    assert current["resumed_pending_job"] is False
    assert current_http.post_calls == [
        (
            DOWNLOAD_TRANSACTIONS_URL,
            build_daily_transaction_download_request("2026-07-28"),
            30.0,
        )
    ]
    assert Path(current["snapshot_path"]).name == "transaction_snapshot_20260728.zip"
    completed = json.loads(
        (output / PENDING_JOB_JOURNAL_NAME).read_text(encoding="utf-8")
    )
    assert completed["state"] == "completed"
    assert completed["run_date"] == "2026-07-28"


def test_daily_producer_cross_date_invalid_receipt_remains_fail_closed(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    first_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "running"}],
    )
    fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=first_http.post,
        http_get=first_http.get,
        now_fn=_clock("2026-07-27T23:55:00Z"),
        max_status_polls=1,
    )
    journal_path = output / PENDING_JOB_JOURNAL_NAME
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    journal["receipt"]["download_request"]["limit"] = 4999
    journal_path.write_text(json.dumps(journal), encoding="utf-8")
    network_calls: list[str] = []

    def network_call(*_args, **_kwargs):
        network_calls.append("called")
        return {}

    invalid = fetch_daily_transaction_snapshot(
        "2026-07-28",
        output,
        http_post=network_call,
        http_get=network_call,
        now_fn=_clock("2026-07-28T00:05:00Z"),
    )

    assert invalid["status"] == "unavailable"
    assert invalid["pending_job_validation_status"] == "invalid"
    assert network_calls == []


def test_daily_producer_cross_date_expired_receipt_reposts_or_stays_stale(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    first_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "running"}],
    )
    fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=first_http.post,
        http_get=first_http.get,
        now_fn=_clock("2026-07-27T00:00:00Z"),
        max_status_polls=1,
    )
    network_calls: list[str] = []

    def network_call(*_args, **_kwargs):
        network_calls.append("called")
        return {}

    expired = fetch_daily_transaction_snapshot(
        "2026-07-28",
        output,
        http_post=network_call,
        http_get=network_call,
        now_fn=_clock("2026-07-28T00:00:01Z"),
    )

    assert expired["status"] == "stale"
    assert expired["pending_job_validation_status"] == "expired"
    assert network_calls == ["called"]


def test_daily_producer_recovers_expired_pending_receipt_with_fresh_post(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    first_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "running"}],
    )
    fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=first_http.post,
        http_get=first_http.get,
        now_fn=_clock("2026-07-27T00:00:00Z"),
        max_status_polls=1,
    )

    fresh_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("B")]),
        statuses=[{"status": "finished"}],
    )
    recovered = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=fresh_http.post,
        http_get=fresh_http.get,
        now_fn=_clock("2026-07-28T00:00:01Z", "2026-07-28T00:00:02Z"),
    )

    assert recovered["status"] == "ok"
    assert recovered["run_date"] == "2026-07-27"
    assert recovered["resumed_pending_job"] is False
    assert recovered["pending_job_validation_status"] == "validated"
    assert fresh_http.post_calls == [
        (
            DOWNLOAD_TRANSACTIONS_URL,
            build_daily_transaction_download_request("2026-07-27"),
            30.0,
        )
    ]
    assert [url for url, _ in fresh_http.get_calls] == [
        fresh_http.status_url,
        fresh_http.file_url,
    ]
    journal = json.loads(
        (output / PENDING_JOB_JOURNAL_NAME).read_text(encoding="utf-8")
    )
    assert journal["state"] == "completed"
    assert journal["run_date"] == "2026-07-27"


def test_daily_producer_cross_date_future_receipt_remains_fail_closed(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    first_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "running"}],
    )
    fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=first_http.post,
        http_get=first_http.get,
        now_fn=_clock("2026-07-27T23:55:00Z"),
        max_status_polls=1,
    )
    journal_path = output / PENDING_JOB_JOURNAL_NAME
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    journal["receipt"]["job_requested_at_utc"] = "2026-07-28T00:10:00Z"
    journal_path.write_text(json.dumps(journal), encoding="utf-8")
    network_calls: list[str] = []

    def network_call(*_args, **_kwargs):
        network_calls.append("called")
        return {}

    future = fetch_daily_transaction_snapshot(
        "2026-07-28",
        output,
        http_post=network_call,
        http_get=network_call,
        now_fn=_clock("2026-07-28T00:05:00Z"),
    )

    assert future["status"] == "unavailable"
    assert future["pending_job_validation_status"] == "invalid"
    assert "future-dated" in future["error"]
    assert network_calls == []


def test_daily_producer_durable_receipt_survives_status_get_failure_without_repost(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    first_http = _FakeProducerHttp(zip_payload=_zip_bytes([_row("A")]))

    def broken_status_get(*_args, **_kwargs):
        raise TimeoutError("status endpoint timed out")

    first = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=first_http.post,
        http_get=broken_status_get,
        now_fn=_clock("2026-07-27T12:00:00Z"),
    )
    assert first["status"] == "pending"
    assert first["job_status"] == "submitted"
    assert first["status_history"] == []
    assert (output / PENDING_JOB_JOURNAL_NAME).is_file()

    post_calls: list[str] = []

    def unexpected_post(*_args, **_kwargs):
        post_calls.append("post")
        return {}

    resumed_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "finished"}],
    )
    resumed = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=unexpected_post,
        http_get=resumed_http.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:01:00Z", "2026-07-27T12:01:01Z"),
    )

    assert resumed["status"] == "ok"
    assert resumed["resumed_pending_job"] is True
    assert len(first_http.post_calls) == 1
    assert post_calls == []


def test_daily_producer_durable_receipt_retries_finished_download_without_repost(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    first_http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "finished"}],
    )

    def broken_file_get(url: str, *, timeout: float):
        first_http.get_calls.append((url, timeout))
        if url == first_http.status_url:
            return {"status": "finished"}
        if url == first_http.file_url:
            raise TimeoutError("file endpoint timed out")
        raise AssertionError(f"unexpected GET URL: {url}")

    first = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=first_http.post,
        http_get=broken_file_get,
        now_fn=_clock("2026-07-27T12:00:00Z"),
    )
    assert first["status"] == "pending"
    assert first["job_status"] == "finished"
    assert first["status_history"] == ["finished"]

    post_calls: list[str] = []

    def unexpected_post(*_args, **_kwargs):
        post_calls.append("post")
        return {}

    resumed_http = _FakeProducerHttp(zip_payload=_zip_bytes([_row("A")]))
    resumed = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=unexpected_post,
        http_get=resumed_http.get,
        now_fn=_clock("2026-07-27T12:01:00Z", "2026-07-27T12:01:01Z"),
    )

    assert resumed["status"] == "ok"
    assert resumed["resumed_pending_job"] is True
    assert resumed["attempt_poll_count"] == 0
    assert post_calls == []
    assert [url for url, _ in resumed_http.get_calls] == [resumed_http.file_url]


@pytest.mark.parametrize("invalid_field", ["status_url", "download_request"])
def test_daily_producer_quarantines_invalid_pending_receipt_without_http(
    tmp_path: Path,
    invalid_field: str,
):
    output = tmp_path / invalid_field
    http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "running"}],
    )
    pending = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=http.post,
        http_get=http.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:00:00Z"),
        max_status_polls=1,
    )
    persist_producer_health_summary(
        run_date="2026-07-27",
        producer_result=pending,
        output_dir=output,
    )
    journal_path = output / PENDING_JOB_JOURNAL_NAME
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    receipt = journal["receipt"]
    if invalid_field == "status_url":
        receipt["status_url"] = "https://evil.example/status"
    else:
        receipt["download_request"]["limit"] = 4999
    journal_path.write_text(json.dumps(journal), encoding="utf-8")

    network_calls: list[str] = []

    def network_call(*_args, **_kwargs):
        network_calls.append("called")
        return {}

    invalid = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=network_call,
        http_get=network_call,
        now_fn=_clock("2026-07-27T12:05:00Z"),
    )
    assert invalid["status"] == "unavailable"
    assert invalid["pending_job_validation_status"] == "invalid"
    assert "pending job" in invalid["error"]
    assert network_calls == []

    persisted = persist_producer_health_summary(
        run_date="2026-07-27",
        producer_result=invalid,
        output_dir=output,
    )
    assert persisted["pending_job_validation_status"] == "invalid"
    quarantined = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=network_call,
        http_get=network_call,
        now_fn=_clock("2026-07-27T12:06:00Z"),
    )
    assert quarantined["status"] == "unavailable"
    assert quarantined["pending_job_validation_status"] == "invalid"
    assert network_calls == []


def test_daily_producer_expired_pending_receipt_stays_stale_when_fresh_post_fails(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "running"}],
    )
    pending = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=http.post,
        http_get=http.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:00:00Z"),
        max_status_polls=1,
    )
    persist_producer_health_summary(
        run_date="2026-07-27",
        producer_result=pending,
        output_dir=output,
    )
    network_calls: list[str] = []

    def network_call(*_args, **_kwargs):
        network_calls.append("called")
        return {}

    expired = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=network_call,
        http_get=network_call,
        now_fn=_clock("2026-07-28T12:00:01Z"),
    )
    assert expired["status"] == "stale"
    assert expired["pending_job_validation_status"] == "expired"
    assert "expired" in expired["error"]
    assert "fresh request failed" in expired["error"]
    assert network_calls == ["called"]


def test_daily_producer_caps_cumulative_pending_status_history(tmp_path: Path):
    output = tmp_path / "observer"
    http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "running"}],
    )
    fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=http.post,
        http_get=http.get,
        now_fn=_clock("2026-07-27T12:00:00Z"),
        max_status_polls=1,
    )
    journal_path = output / PENDING_JOB_JOURNAL_NAME
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    journal["receipt"]["status_history"] = ["running"] * 256
    journal["receipt"]["status_poll_count"] = 256
    journal_path.write_text(json.dumps(journal), encoding="utf-8")
    network_calls: list[str] = []

    def network_call(*_args, **_kwargs):
        network_calls.append("called")
        return {}

    bounded = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=network_call,
        http_get=network_call,
        now_fn=_clock("2026-07-27T12:01:00Z"),
    )
    assert bounded["status"] == "pending"
    assert bounded["status_poll_count"] == 256
    assert bounded["attempt_poll_count"] == 0
    assert "bounded limit" in bounded["error"]
    assert network_calls == []


def test_daily_producer_rejects_backward_retrieval_clock(tmp_path: Path):
    http = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "finished"}],
    )
    result = fetch_daily_transaction_snapshot(
        "2026-07-27",
        tmp_path / "observer",
        http_post=http.post,
        http_get=http.get,
        now_fn=_clock("2026-07-27T12:00:00Z", "2026-07-27T11:59:59Z"),
    )

    assert result["status"] == "unavailable"
    assert result["pending_job_validation_status"] == "invalid"
    assert "clock moved backward" in result["error"]
    assert result["snapshot_path"] is None
    assert result["manifest_path"] is None


def test_daily_producer_converts_failed_job_and_http_errors_to_unavailable(
    tmp_path: Path,
):
    failed = _FakeProducerHttp(
        zip_payload=_zip_bytes([_row("A")]),
        statuses=[{"status": "failed"}],
    )
    result = fetch_daily_transaction_snapshot(
        "2026-07-27",
        tmp_path / "failed",
        http_post=failed.post,
        http_get=failed.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:00:00Z"),
    )
    assert result["status"] == "unavailable"
    assert result["job_status"] == "failed"
    assert "failed" in result["error"]

    def broken_post(*_args, **_kwargs):
        raise TimeoutError("upstream timeout")

    network = fetch_daily_transaction_snapshot(
        "2026-07-27",
        tmp_path / "network",
        http_post=broken_post,
        now_fn=_clock("2026-07-27T12:00:00Z"),
    )
    assert network["status"] == "unavailable"
    assert "TimeoutError" in network["error"]


@pytest.mark.parametrize(
    ("overrides", "zip_payload", "error_fragment"),
    [
        (
            {"file_url": "https://evil.example/download.zip"},
            b"unused",
            "official USAspending host",
        ),
        (
            {"status_url": "http://api.usaspending.gov/status"},
            b"unused",
            "official USAspending host",
        ),
        (
            {},
            _zip_bytes([_row("A")], member_name="Other.csv"),
            "Contracts_PrimeTransactions",
        ),
        (
            {},
            _zip_bytes([_row("A")], header=["unrelated_column"]),
            "missing required columns",
        ),
    ],
)
def test_daily_producer_rejects_unofficial_hosts_and_invalid_zip_contract(
    tmp_path: Path,
    overrides: dict,
    zip_payload: bytes,
    error_fragment: str,
):
    http = _FakeProducerHttp(
        zip_payload=zip_payload,
        initial_overrides=overrides,
    )
    result = fetch_daily_transaction_snapshot(
        "2026-07-27",
        tmp_path / error_fragment.replace(" ", "_"),
        http_post=http.post,
        http_get=http.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:00:00Z", "2026-07-27T12:00:01Z"),
    )

    assert result["status"] == "unavailable"
    assert error_fragment in result["error"]
    assert result["snapshot_path"] is None


def test_health_uses_manifest_clock_and_marks_zero_new_forward_as_heartbeat(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    http = _FakeProducerHttp(zip_payload=_zip_bytes([_row("A")]))
    producer = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=http.post,
        http_get=http.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:00:00Z", "2026-07-27T12:00:01Z"),
    )
    observer = persist_usaspending_obligation_observer(
        producer["snapshot_path"],
        observed_at=producer["retrieved_at_utc"],
        output_root=output,
    )

    summary = persist_producer_health_summary(
        run_date="2026-07-27",
        producer_result=producer,
        observer_summary=observer,
        output_dir=output,
    )

    assert summary["status"] == "ok"
    assert summary["producer_status"] == "ok"
    assert summary["snapshot_fresh"] is True
    assert summary["heartbeat_status"] == "fresh_success_zero_forward"
    assert summary["zero_event_heartbeat"] is True
    assert summary["retrieved_at_utc"] == producer["retrieved_at_utc"]
    assert summary["manifest_path"] == producer["manifest_path"]
    assert summary["producer_health"]["parsed_transaction_count"] == 1
    assert summary["producer_health"]["snapshot_row_count"] == 1
    assert summary["last_producer_success_at_utc"] == producer["retrieved_at_utc"]
    rows = _ledger(output / "ledger.jsonl")
    assert rows[0]["first_seen_at"] == producer["retrieved_at_utc"]


def test_health_preserves_last_success_when_next_producer_attempt_is_unavailable(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    http = _FakeProducerHttp(zip_payload=_zip_bytes([_row("A")]))
    producer = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=http.post,
        http_get=http.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:00:00Z", "2026-07-27T12:00:01Z"),
    )
    observer = persist_usaspending_obligation_observer(
        producer["snapshot_path"],
        observed_at=producer["retrieved_at_utc"],
        output_root=output,
    )
    first = persist_producer_health_summary(
        run_date="2026-07-27",
        producer_result=producer,
        observer_summary=observer,
        output_dir=output,
    )
    unavailable = {
        "status": "unavailable",
        "producer_mode": PRODUCER_MODE,
        "source_mode": "official_producer",
        "requested_at_utc": "2026-07-28T12:00:00Z",
        "error": "upstream timeout",
    }

    second = persist_producer_health_summary(
        run_date="2026-07-28",
        producer_result=unavailable,
        output_dir=output,
    )

    assert second["status"] == "unavailable"
    assert second["snapshot_fresh"] is False
    assert second["zero_event_heartbeat"] is False
    assert second["heartbeat_status"] == "producer_unavailable"
    assert (
        second["last_producer_success_at_utc"]
        == first["last_producer_success_at_utc"]
    )
    assert second["producer_health"]["last_success_manifest_sha256"] == producer[
        "manifest_sha256"
    ]


def test_health_never_marks_unverified_local_override_as_fresh(tmp_path: Path):
    local_snapshot = _write_zip(tmp_path / "local.zip", [_row("A")])
    observer_summary = {
        "status": "ok",
        "observed_at": "2026-07-27T12:00:00Z",
        "parsed_transaction_count": 1,
        "rows_appended": 0,
        "new_forward_rows_appended": 0,
    }

    summary = persist_producer_health_summary(
        run_date="2026-07-27",
        producer_result={
            "status": "ok",
            "producer_mode": "configured_local_snapshot",
            "source_mode": "configured_local_snapshot",
            "snapshot_path": str(local_snapshot),
            "retrieved_at_utc": "2026-07-27T12:00:00Z",
        },
        observer_summary=observer_summary,
        output_dir=tmp_path / "observer",
    )

    assert summary["status"] == "unavailable"
    assert summary["producer_status"] == "unverified_local_override"
    assert summary["heartbeat_status"] == "unverified_local_override"
    assert summary["snapshot_fresh"] is False
    assert summary["zero_event_heartbeat"] is False


def test_health_fails_closed_on_manifest_clock_or_parse_count_mismatch(
    tmp_path: Path,
):
    output = tmp_path / "observer"
    http = _FakeProducerHttp(zip_payload=_zip_bytes([_row("A")]))
    producer = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=http.post,
        http_get=http.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:00:00Z", "2026-07-27T12:00:01Z"),
    )
    base_observer = {
        "status": "ok",
        "observed_at": producer["retrieved_at_utc"],
        "parsed_transaction_count": 1,
        "rows_appended": 0,
        "new_forward_rows_appended": 0,
    }

    parse_mismatch = persist_producer_health_summary(
        run_date="2026-07-27",
        producer_result=producer,
        observer_summary={**base_observer, "parsed_transaction_count": 0},
        output_dir=output,
    )
    assert parse_mismatch["status"] == "unavailable"
    assert parse_mismatch["heartbeat_status"] == "observer_parse_count_mismatch"
    assert parse_mismatch["zero_event_heartbeat"] is False

    clock_mismatch = persist_producer_health_summary(
        run_date="2026-07-27",
        producer_result=producer,
        observer_summary={
            **base_observer,
            "observed_at": "2026-07-27T12:00:02Z",
        },
        output_dir=output,
    )
    assert clock_mismatch["status"] == "unavailable"
    assert clock_mismatch["heartbeat_status"] == "observer_clock_manifest_mismatch"
    assert clock_mismatch["snapshot_fresh"] is False


def test_health_treats_zero_source_rows_as_starvation_not_heartbeat(tmp_path: Path):
    output = tmp_path / "observer"
    http = _FakeProducerHttp(zip_payload=_zip_bytes([]))
    producer = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=http.post,
        http_get=http.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:00:00Z", "2026-07-27T12:00:01Z"),
    )
    assert producer["status"] == "ok"
    assert producer["row_count"] == 0

    summary = persist_producer_health_summary(
        run_date="2026-07-27",
        producer_result=producer,
        observer_summary={
            "status": "ok",
            "observed_at": producer["retrieved_at_utc"],
            "parsed_transaction_count": 0,
            "rows_appended": 0,
            "new_forward_rows_appended": 0,
        },
        output_dir=output,
    )

    assert summary["status"] == "unavailable"
    assert summary["heartbeat_status"] == "source_zero_rows"
    assert summary["zero_event_heartbeat"] is False
    assert summary["snapshot_fresh"] is False


def test_health_revalidates_immutable_manifest_hash(tmp_path: Path):
    output = tmp_path / "observer"
    http = _FakeProducerHttp(zip_payload=_zip_bytes([_row("A")]))
    producer = fetch_daily_transaction_snapshot(
        "2026-07-27",
        output,
        http_post=http.post,
        http_get=http.get,
        sleep_fn=lambda _seconds: None,
        now_fn=_clock("2026-07-27T12:00:00Z", "2026-07-27T12:00:01Z"),
    )
    manifest_path = Path(producer["manifest_path"])
    manifest_path.write_bytes(manifest_path.read_bytes() + b"\n")

    summary = persist_producer_health_summary(
        run_date="2026-07-27",
        producer_result=producer,
        observer_summary={
            "status": "ok",
            "observed_at": producer["retrieved_at_utc"],
            "parsed_transaction_count": 1,
            "rows_appended": 0,
            "new_forward_rows_appended": 0,
        },
        output_dir=output,
    )

    assert summary["status"] == "unavailable"
    assert summary["heartbeat_status"] == "producer_manifest_unverified"
    assert summary["snapshot_fresh"] is False
