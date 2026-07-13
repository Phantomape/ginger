from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from drugsfda_approval_observer import (  # noqa: E402
    APPROVAL_DATE_ROLE,
    HISTORICAL_PIT_STATUS,
    parse_drugsfda_approval_snapshot,
    persist_daily_drugsfda_approval_observer,
    persist_drugsfda_approval_observer,
)


def _write_table(
    archive: zipfile.ZipFile, name: str, header: list[str], rows: list[list[str]]
) -> None:
    text = "\r\n".join(
        ["\t".join(header), *("\t".join(row) for row in rows)]
    ) + "\r\n"
    archive.writestr(name, text.encode("cp1252"))


def _synthetic_zip(path: Path, *, include_new_application: bool = False) -> Path:
    applications = [
        ["000001", "NDA", "", "O’NEIL PHARMA"],
        ["000002", "BLA", "", "BIO SPONSOR"],
        ["000003", "ANDA", "", "GENERIC SPONSOR"],
        ["000004", "NDA", "", "NOT APPROVED"],
        ["000005", "NDA", "", "SUPPLEMENT ONLY"],
    ]
    products = [
        ["000001", "001", "TABLET", "1MG", "0", "DRUG A", "INGREDIENT A", "0"],
        ["000001", "002", "TABLET", "2MG", "0", "DRUG A PLUS", "INGREDIENT A; INGREDIENT B", "0"],
        ["000001", "003", "TABLET", "3MG", "0", "DRUG A", "INGREDIENT A", "0"],
        ["000002", "001", "INJECTABLE", "1ML", "0", "BIO B", "BIO INGREDIENT", "0"],
        ["000003", "001", "TABLET", "1MG", "0", "ANDA C", "GENERIC C", "0"],
    ]
    submissions = [
        ["000001", "1", "ORIG", "1", "AP", "2021-05-03 00:00:00", "", "STANDARD"],
        ["000001", "1", "ORIG", "2", "AP", "2020-01-02 00:00:00", "", "STANDARD"],
        ["000001", "3", "SUPPL", "3", "AP", "2019-01-01 00:00:00", "", "STANDARD"],
        ["000002", "1", "ORIG", "1", "AP", "2022-06-07 00:00:00", "", "PRIORITY"],
        ["000003", "1", "ORIG", "1", "AP", "2020-02-02 00:00:00", "", "STANDARD"],
        ["000004", "1", "ORIG", "1", "TA", "2020-03-03 00:00:00", "", "STANDARD"],
        ["000005", "3", "SUPPL", "1", "AP", "2020-04-04 00:00:00", "", "STANDARD"],
    ]
    if include_new_application:
        applications.append(["000006", "BLA", "", "NEW BIO"])
        products.append(
            ["000006", "001", "INJECTABLE", "1ML", "0", "BIO NEW", "NEW INGREDIENT", "0"]
        )
        submissions.append(
            ["000006", "1", "ORIG", "1", "AP", "2024-08-09 00:00:00", "", "PRIORITY"]
        )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        _write_table(
            archive,
            "Applications.txt",
            ["ApplNo", "ApplType", "ApplPublicNotes", "SponsorName"],
            applications,
        )
        _write_table(
            archive,
            "Products.txt",
            [
                "ApplNo",
                "ProductNo",
                "Form",
                "Strength",
                "ReferenceDrug",
                "DrugName",
                "ActiveIngredient",
                "ReferenceStandard",
            ],
            products,
        )
        _write_table(
            archive,
            "Submissions.txt",
            [
                "ApplNo",
                "SubmissionClassCodeID",
                "SubmissionType",
                "SubmissionNo",
                "SubmissionStatus",
                "SubmissionStatusDate",
                "SubmissionsPublicNotes",
                "ReviewPriority",
            ],
            submissions,
        )
    return path


def _ledger(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_parse_original_approved_nda_bla_and_dedupe_application(tmp_path: Path):
    source = _synthetic_zip(tmp_path / "drugs.zip")

    rows = parse_drugsfda_approval_snapshot(source)

    assert [(row["appl_type"], row["appl_no"]) for row in rows] == [
        ("NDA", "000001"),
        ("BLA", "000002"),
    ]
    nda, bla = rows
    assert nda["approval_date"] == "2020-01-02"
    assert nda["approval_date_role"] == APPROVAL_DATE_ROLE
    assert nda["qualifying_original_approved_submission_rows"] == 2
    assert nda["sponsor_name"] == "O’NEIL PHARMA"
    assert nda["product_names"] == ["DRUG A", "DRUG A PLUS"]
    assert nda["active_ingredients"] == [
        "INGREDIENT A",
        "INGREDIENT A; INGREDIENT B",
    ]
    assert bla["approval_date"] == "2022-06-07"
    assert all(row["historical_pit_status"] == HISTORICAL_PIT_STATUS for row in rows)


def test_persist_uses_retrieval_utc_not_approval_date_and_rerun_is_idempotent(
    tmp_path: Path,
):
    source = _synthetic_zip(tmp_path / "drugs.zip")
    output = tmp_path / "observer"

    first = persist_drugsfda_approval_observer(
        "20260713",
        raw_zip_path=source,
        output_root=output,
        observed_at="2026-07-13T11:42:35Z",
    )
    first_ledger_bytes = (output / "ledger.jsonl").read_bytes()
    second = persist_daily_drugsfda_approval_observer(
        "20260713",
        raw_zip_path=source,
        output_root=output,
        observed_at="2026-07-13T12:42:35Z",
    )

    assert first["parsed_application_count"] == 2
    assert first["parsed_application_type_counts"] == {"BLA": 1, "NDA": 1}
    assert first["historical_seed_count"] == 2
    assert first["historical_seed_rows_appended"] == 2
    assert first["new_forward_event_count"] == 0
    assert first["forward_event_count_total"] == 0
    assert first["new_application_count"] == 0
    assert first["rows_appended"] == 2
    assert second["historical_seed_count"] == 2
    assert second["historical_seed_rows_appended"] == 0
    assert second["new_forward_event_count"] == 0
    assert second["new_application_count"] == 0
    assert second["rows_appended"] == 0
    assert second["ledger_row_count"] == 2
    assert (output / "ledger.jsonl").read_bytes() == first_ledger_bytes

    rows = _ledger(output / "ledger.jsonl")
    assert len({row["application_id"] for row in rows}) == 2
    assert all(row["first_seen_at"] == "2026-07-13T11:42:35Z" for row in rows)
    assert all(row["first_seen_at"] != row["approval_date"] for row in rows)
    assert all(row["availability_timestamp_field"] == "first_seen_at" for row in rows)
    assert all(row["availability_timestamp_source"] == "snapshot_retrieval_utc" for row in rows)
    assert all(row["historical_pit_status"] == HISTORICAL_PIT_STATUS for row in rows)
    assert all(row["observer_only"] is True for row in rows)
    assert all(row["trade_enabled"] is False for row in rows)
    assert all(row["forward_event"] is False for row in rows)
    assert all(row["candidate_eligible"] is False for row in rows)
    assert all(row["prospective_evidence_eligible"] is False for row in rows)
    assert all(row["forward_eligibility_status"] == "seed_not_forward" for row in rows)
    assert all(row["seed_not_forward"] is True for row in rows)
    assert all(row["seed_status"] == "historical_snapshot_seed_not_forward" for row in rows)
    assert all(row["candidate_tickers"] == [] and row["ticker"] is None for row in rows)
    assert all(row["entry_date"] is None and row["entry_rule"] is None for row in rows)
    assert all(row["entry_status"] == "not_applicable_historical_snapshot_seed" for row in rows)
    assert all(row["outcome_status"] == "not_applicable_historical_snapshot_seed" for row in rows)
    assert all(row["target_price"] is None for row in rows)
    assert not list(output.glob("*.tmp"))


def test_later_snapshot_appends_only_new_application(tmp_path: Path):
    first_source = _synthetic_zip(tmp_path / "first.zip")
    second_source = _synthetic_zip(
        tmp_path / "second.zip", include_new_application=True
    )
    output = tmp_path / "observer"

    persist_drugsfda_approval_observer(
        raw_zip_path=first_source,
        output_root=output,
        observed_at="2026-07-13T11:42:35Z",
    )
    first_bytes = (output / "ledger.jsonl").read_bytes()
    summary = persist_drugsfda_approval_observer(
        raw_zip_path=second_source,
        output_root=output,
        observed_at="2026-07-14T11:42:35Z",
    )

    assert summary["parsed_application_count"] == 3
    assert summary["historical_seed_count"] == 2
    assert summary["new_forward_event_count"] == 1
    assert summary["forward_event_count_total"] == 1
    assert summary["new_application_count"] == 1
    assert summary["rows_appended"] == 1
    assert summary["ledger_row_count"] == 3
    current = (output / "ledger.jsonl").read_bytes()
    assert current.startswith(first_bytes)
    rows = _ledger(output / "ledger.jsonl")
    assert rows[-1]["appl_no"] == "000006"
    assert rows[-1]["first_seen_at"] == "2026-07-14T11:42:35Z"
    assert rows[-1]["forward_event"] is True
    assert rows[-1]["prospective_evidence_eligible"] is True
    assert rows[-1]["candidate_eligible"] is False
    assert rows[-1]["forward_eligibility_status"] == "prospective_first_seen"
    assert rows[-1]["seed_not_forward"] is False
    assert rows[-1]["seed_status"] is None
    assert rows[-1]["entry_status"].startswith("pending")
    assert rows[-1]["outcome_status"] == "pending"
