from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent))

from usaspending_obligation_observer import (  # noqa: E402
    ELIGIBILITY_RULE,
    HISTORICAL_PIT_STATUS,
    main,
    parse_usaspending_transaction_snapshot,
    persist_daily_usaspending_obligation_observer,
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
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(CANONICAL_HEADER)
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Contracts_Subawards.csv", "ignored\n")
        archive.writestr(
            "Contracts_PrimeTransactions_1.csv",
            text.getvalue().encode("utf-8-sig"),
        )
    return path


def _ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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
