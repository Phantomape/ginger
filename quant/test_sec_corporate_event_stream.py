import json
from datetime import date

from sec_corporate_event_stream import (
    append_rows,
    build_event_rows,
    daily_index_url,
    ingest_range,
    parse_daily_index,
    quarterly_cache_path,
    quarterly_index_url,
)

SAMPLE_IDX = """Description:           Daily Index of EDGAR Dissemination Feed by Form Type
Last Data Received:     July 1, 2026

Form Type   Company Name                                                  CIK         Date Filed  File Name
---------------------------------------------------------------------------------------------------------------
10-K        Example Annual Filer                                          1000001     20260701    edgar/data/1000001/0000000000-26-000001.txt
425         Alcoa Corp                                                    1675149     20260701    edgar/data/1675149/0000950103-26-009900.txt
S-1         SpaceLaunch Holdings Inc                                      2222222     20260701    edgar/data/2222222/0001111111-26-000010.txt
S-1/A       SpaceLaunch Holdings Inc                                      2222222     20260701    edgar/data/2222222/0001111111-26-000011.txt
F-1         Foreign Newco PLC                                             3333333     20260701    edgar/data/3333333/0002222222-26-000012.txt
8-K         Example Current Filer                                         1000002     20260701    edgar/data/1000002/0000000000-26-000002.txt
"""


SAMPLE_QUARTERLY_IDX = (
    "Description:           Master Index of EDGAR Dissemination Feed by Form Type\r\n"
    "\r\n"
    "Form Type   Company Name                                                  CIK         Date Filed  File Name\r\n"
    "---------------------------------------------------------------------------------------------------------\r\n"
    "1-A              AETHLON MEDICAL INC                                           882291      2024-12-27  edgar/data/882291/0001683168-24-009014.txt          \r\n"
    "S-1              Newly Private Co Inc.                                         2044436     2024-11-19  edgar/data/2044436/0002044436-24-000001.txt         \r\n"
    "425              Merger Talker Corp                                            1861089     2024-10-15  edgar/data/1861089/0001477932-24-006396.txt         \r\n"
)


def test_parse_daily_index_extracts_all_rows():
    rows = parse_daily_index(SAMPLE_IDX)
    assert len(rows) == 6
    assert rows[0]["form_type"] == "10-K"
    assert rows[1]["company_name"] == "Alcoa Corp"
    assert rows[1]["cik"] == "1675149"
    assert rows[1]["date_filed"] == "20260701"


def test_parse_quarterly_index_misaligned_header():
    rows = parse_daily_index(SAMPLE_QUARTERLY_IDX)
    assert len(rows) == 3
    assert rows[1]["form_type"] == "S-1"
    assert rows[1]["company_name"] == "Newly Private Co Inc."
    assert rows[1]["cik"] == "2044436"
    assert rows[1]["date_filed"] == "2024-11-19"
    events = build_event_rows(rows, source_index_file="q", ticker_map={})
    assert [e["form_type"] for e in events] == ["S-1", "425"]
    assert events[0]["filed_date"] == "2024-11-19"


def test_build_event_rows_filters_and_classifies():
    events = build_event_rows(
        parse_daily_index(SAMPLE_IDX),
        source_index_file="https://example.test/form.20260701.idx",
        ticker_map={"0001675149": {"ticker": "AA"}},
    )
    assert [e["form_type"] for e in events] == ["425", "S-1", "S-1/A", "F-1"]
    by_form = {e["form_type"]: e for e in events}
    assert by_form["425"]["event_class"] == "merger_communication"
    assert by_form["S-1"]["event_class"] == "ipo_registration"
    assert by_form["S-1"]["is_amendment"] is False
    assert by_form["S-1/A"]["is_amendment"] is True
    assert by_form["425"]["ticker"] == "AA"
    assert by_form["425"]["ticker_status"] == "resolved"
    assert by_form["S-1"]["ticker"] is None
    assert by_form["S-1"]["ticker_status"] == "unresolved"
    assert by_form["S-1"]["filed_date"] == "2026-07-01"
    assert by_form["S-1"]["accession"] == "0001111111-26-000010"


def test_append_rows_is_idempotent(tmp_path):
    rows_path = tmp_path / "rows.jsonl"
    events = build_event_rows(
        parse_daily_index(SAMPLE_IDX), source_index_file="x", ticker_map={}
    )
    assert append_rows(rows_path, events) == 4
    assert append_rows(rows_path, events) == 0
    lines = [json.loads(l) for l in rows_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 4


def test_index_url_quarter_mapping():
    assert daily_index_url(date(2026, 7, 1)).endswith(
        "/2026/QTR3/form.20260701.idx"
    )
    assert quarterly_index_url(2024, 4).endswith("/2024/QTR4/form.idx")
    assert quarterly_index_url(2026, 3).endswith("/2026/QTR3/form.idx")


def test_ingest_range_uses_quarter_cache_and_manifest(tmp_path):
    cache_dir = tmp_path / "cache"
    out_dir = tmp_path / "out"
    cache_dir.mkdir(parents=True)
    quarterly_cache_path(2026, 3, cache_dir).write_text(
        SAMPLE_IDX, encoding="latin-1"
    )

    # today inside a LATER quarter -> 2026 QTR3 is complete, cache is trusted
    summary = ingest_range(
        date(2026, 7, 1),
        date(2026, 7, 2),
        out_dir=out_dir,
        cache_dir=cache_dir,
        ticker_map={"0001675149": {"ticker": "AA"}},
        today=date(2026, 10, 5),
    )
    assert summary["rows_appended"] == 4
    assert summary["quarters_fetched"] == 0

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["quarter_status"]["2026QTR3"]["status"] == "ingested"
    assert manifest["quarter_status"]["2026QTR3"]["complete"] is True

    # second run: completed quarter skipped entirely, nothing re-appended
    summary2 = ingest_range(
        date(2026, 7, 1),
        date(2026, 7, 2),
        out_dir=out_dir,
        cache_dir=cache_dir,
        ticker_map={},
        today=date(2026, 10, 5),
    )
    assert summary2["rows_appended"] == 0
    assert summary2["quarters_fetched"] == 0


def test_ingest_range_filters_by_filed_date(tmp_path):
    cache_dir = tmp_path / "cache"
    out_dir = tmp_path / "out"
    cache_dir.mkdir(parents=True)
    quarterly_cache_path(2026, 3, cache_dir).write_text(
        SAMPLE_IDX, encoding="latin-1"
    )
    # requested range ends before the sample rows' filed_date 2026-07-01... use
    # a range that excludes them
    summary = ingest_range(
        date(2026, 8, 1),
        date(2026, 8, 31),
        out_dir=out_dir,
        cache_dir=cache_dir,
        ticker_map={},
        today=date(2026, 10, 5),
    )
    assert summary["rows_appended"] == 0
