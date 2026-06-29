from __future__ import annotations

import json
from pathlib import Path

import form144_planned_sale_context as form144


def test_parse_form144_text_extracts_planned_sale_fields():
    text = """
    <html><body>
    Name of Person for Whose Account the Securities are To Be Sold: Jane Doe
    Relationship to Issuer: Chief Financial Officer
    Title of Class: Common Stock
    Number of Shares or Other Units To Be Sold: 125,000
    Aggregate Market Value: $3,750,000
    Approximate Date of Sale: 06/17/2026
    </body></html>
    """

    parsed = form144.parse_form144_text(text)

    assert parsed["parse_status"] == "parsed"
    assert parsed["planned_sale_shares"] == 125000
    assert parsed["planned_sale_value_usd"] == 3750000
    assert parsed["planned_sale_period_start"] == "2026-06-17"
    assert parsed["seller_name"] == "Jane Doe"
    assert parsed["relationship_to_issuer"] == "Chief Financial Officer"


def test_persist_form144_context_uses_cached_document_and_adv_ratio(tmp_path):
    form_index_dir = tmp_path / "form_index"
    form_index_dir.mkdir()
    index_file = form_index_dir / "form_2026_QTR2.idx"
    index_file.write_text(
        "144              Example Issuer Inc.                                           1234567     2026-06-15  edgar/data/1234567/0001234567-26-000001.txt         \n",
        encoding="utf-8",
    )
    company_tickers = tmp_path / "sec_company_tickers.json"
    company_tickers.write_text(
        json.dumps({"0": {"cik_str": 1234567, "ticker": "EXMP", "title": "Example Issuer Inc."}}),
        encoding="utf-8",
    )
    document_cache = tmp_path / "documents"
    document_path = document_cache / "edgar" / "data" / "1234567" / "0001234567-26-000001.txt"
    document_path.parent.mkdir(parents=True)
    document_path.write_text(
        """
        Name of Person for Whose Account the Securities are To Be Sold: Jane Doe
        Relationship to Issuer: Director
        Number of Shares or Other Units To Be Sold: 125,000
        Aggregate Market Value: $3,750,000
        Approximate Date of Sale: June 17, 2026
        """,
        encoding="utf-8",
    )

    summary = form144.persist_form144_planned_sale_context(
        as_of="2026-06-18",
        data_dir=tmp_path / "out",
        lookback_days=10,
        form_index_dir=form_index_dir,
        company_tickers_path=company_tickers,
        document_cache_dirs=[document_cache],
        float_shares_by_ticker={"EXMP": 10_000_000},
        adv20_shares_by_ticker={"EXMP": 250_000},
    )

    assert summary["rows_written"] == 1
    assert summary["rows_with_parseable_planned_sale_to_float"] == 1
    assert summary["rows_with_parseable_planned_sale_to_adv20"] == 1
    rows = [
        json.loads(line)
        for line in Path(summary["output_path"]).read_text(encoding="utf-8").splitlines()
    ]
    row = rows[0]
    assert row["ticker"] == "EXMP"
    assert row["usable_trade_date"] == "2026-06-16"
    assert row["planned_sale_to_float"] == 0.0125
    assert row["planned_sale_to_adv20"] == 0.5
    assert row["planned_sale_bucket"] == "high_planned_sale_overhang"
    assert row["machine_parseable_planned_sale_ratio"] is True

    context = form144.latest_form144_context_for_entry(
        rows=rows,
        ticker="EXMP",
        entry_date="2026-06-18",
        lookback_days=5,
    )
    assert context["eligible_for_forward_outcome_join"] is True
    assert context["form144_high_planned_sale_rows"] == 1
    assert context["form144_max_planned_sale_to_adv20"] == 0.5


def test_index_only_rows_are_not_treated_as_parseable_ratios(tmp_path):
    form_index_dir = tmp_path / "form_index"
    form_index_dir.mkdir()
    (form_index_dir / "form_2026_QTR2.idx").write_text(
        "144              Example Issuer Inc.                                           1234567     2026-06-15  edgar/data/1234567/0001234567-26-000001.txt         \n",
        encoding="utf-8",
    )
    company_tickers = tmp_path / "sec_company_tickers.json"
    company_tickers.write_text(
        json.dumps({"0": {"cik_str": 1234567, "ticker": "EXMP", "title": "Example Issuer Inc."}}),
        encoding="utf-8",
    )

    rows, summary = form144.build_form144_context_rows(
        as_of="2026-06-18",
        lookback_days=10,
        form_index_dir=form_index_dir,
        company_tickers_path=company_tickers,
        document_cache_dirs=[tmp_path / "missing"],
    )

    assert summary["rows_written"] == 1
    assert rows[0]["primary_document_status"] == "missing_cache"
    assert rows[0]["machine_parseable_planned_sale_ratio"] is False
    assert rows[0]["planned_sale_bucket"] == "form144_index_only_document_missing"


def test_materialize_form144_primary_documents_downloads_missing_texts(tmp_path):
    context_path = tmp_path / "form144_planned_sale_context_20260628.jsonl"
    cached_file = "edgar/data/1234567/0001234567-26-000001.txt"
    missing_file = "edgar/data/7654321/0007654321-26-000002.txt"
    rows = [
        {"ticker": "EXMP", "cik": 1234567, "filing_date": "2026-06-15", "accession_number": "0001234567-26-000001", "file_name": cached_file},
        {"ticker": "MISS", "cik": 7654321, "filing_date": "2026-06-16", "accession_number": "0007654321-26-000002", "file_name": missing_file},
        {"ticker": "MISS", "cik": 7654321, "filing_date": "2026-06-16", "accession_number": "0007654321-26-000002", "file_name": missing_file},
    ]
    context_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    cached_path = form144.primary_document_cache_path(cached_file, cache_dir)
    cached_path.parent.mkdir(parents=True)
    cached_path.write_text("already cached", encoding="utf-8")
    fetched_urls = []

    def fake_fetcher(*, url, user_agent):
        fetched_urls.append((url, user_agent))
        return b"downloaded filing text"

    summary = form144.materialize_form144_primary_documents(
        context_path=context_path,
        cache_dir=cache_dir,
        max_documents=5,
        sleep_seconds=0,
        user_agent="test-agent",
        fetcher=fake_fetcher,
    )

    assert summary["status"] == "ok"
    assert summary["unique_primary_documents"] == 2
    assert summary["already_cached"] == 1
    assert summary["attempted_downloads"] == 1
    assert summary["downloaded"] == 1
    assert fetched_urls == [
        (
            "https://www.sec.gov/Archives/edgar/data/7654321/0007654321-26-000002.txt",
            "test-agent",
        )
    ]
    downloaded_path = form144.primary_document_cache_path(missing_file, cache_dir)
    assert downloaded_path.read_bytes() == b"downloaded filing text"
