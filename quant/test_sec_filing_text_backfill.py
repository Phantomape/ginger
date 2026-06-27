from __future__ import annotations

import argparse
import json

import sec_filing_text_backfill as text_backfill
from sec_filing_text_backfill import (
    candidate_documents,
    html_to_text,
    normalize_text,
    parse_dei_cover_status,
)


def test_html_to_text_drops_script_and_decodes_entities() -> None:
    raw = """
    <html><head><style>.x{}</style><script>bad()</script></head>
    <body><p>Revenue&nbsp;rose</p><div>Strong &amp; durable demand.</div></body></html>
    """

    text = html_to_text(raw)

    assert "bad()" not in text
    assert "Revenue rose" in text
    assert "Strong & durable demand" in text


def test_candidate_documents_prioritizes_exhibit_99_and_primary() -> None:
    index_payload = {
        "directory": {
            "item": [
                {"name": "abc-20250101_cal.xml"},
                {"name": "abc-20250101.htm"},
                {"name": "ex99-1.htm"},
                {"name": "abc-20250101_pre.xml"},
                {"name": "picture.jpg"},
            ]
        }
    }

    names = candidate_documents(index_payload, primary_document="abc-20250101.htm", max_documents=3)

    assert names[:2] == ["ex99-1.htm", "abc-20250101.htm"]
    assert "abc-20250101_cal.xml" not in names
    assert "picture.jpg" not in names


def test_candidate_documents_keeps_periodic_cover_xbrl_before_exhibits() -> None:
    index_payload = {
        "directory": {
            "item": [
                {"name": "0000723125-26-000015-index-headers.html"},
                {"name": "mu-20260528.htm"},
                {"name": "ex101-amendmentno3tothedir.htm"},
                {"name": "ex102-amendmentno3tothedir.htm"},
                {"name": "R1.htm"},
                {"name": "mu-20260528_htm.xml"},
                {"name": "mu-20260528_cal.xml"},
                {"name": "FilingSummary.xml"},
            ]
        }
    }

    names = candidate_documents(index_payload, primary_document="mu-20260528.htm", max_documents=4)

    assert names[0] == "mu-20260528.htm"
    assert "R1.htm" in names
    assert "mu-20260528_htm.xml" in names
    assert "mu-20260528_cal.xml" not in names
    assert "FilingSummary.xml" not in names


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  a\n\n b\t c  ") == "a b c"


def test_parse_dei_cover_status_from_inline_xbrl_facts() -> None:
    raw = """
    <ix:nonNumeric name="dei:EntityFilerCategory">Large Accelerated Filer</ix:nonNumeric>
    <ix:nonNumeric name="dei:EntityEmergingGrowthCompany">false</ix:nonNumeric>
    <ix:nonNumeric name="dei:EntityShellCompany">false</ix:nonNumeric>
    """

    status = parse_dei_cover_status(raw)

    assert status["parse_status"] == "parsed_machine_readable_dei_fact"
    assert status["filer_category"] == "large_accelerated_filer"
    assert status["status_booleans"]["large_accelerated_filer"] is True
    assert status["status_booleans"]["accelerated_filer"] is False
    assert status["status_booleans"]["emerging_growth_company"] is False
    assert status["status_booleans"]["shell_company"] is False


def test_parse_dei_cover_status_from_clear_checkbox_text() -> None:
    text = (
        "\u2610 Large accelerated filer "
        "\u2612 Accelerated filer "
        "\u2610 Non-accelerated filer "
        "\u2610 Smaller reporting company"
    )

    status = parse_dei_cover_status(text)

    assert status["parse_status"] == "parsed_cover_page_checkbox_text"
    assert status["status_booleans"]["large_accelerated_filer"] is False
    assert status["status_booleans"]["accelerated_filer"] is True
    assert status["status_booleans"]["non_accelerated_filer"] is False
    assert status["status_booleans"]["smaller_reporting_company"] is False


def test_parse_dei_cover_status_from_column_header_checkbox_table() -> None:
    text = (
        "Indicate by check mark whether the registrant is a large accelerated filer, "
        "an accelerated filer, a non-accelerated filer, a smaller reporting company, "
        "or an emerging growth company. Large Accelerated Filer Accelerated Filer "
        "Non-Accelerated Filer Smaller Reporting Company Emerging Growth Company "
        "\u2612 \u2610 \u2610 \u2610 \u2610 "
        "Indicate by check mark whether the registrant is a shell company "
        "(as defined in Rule 12b-2 of the Exchange Act). Yes \u2610 No \u2612"
    )

    status = parse_dei_cover_status(text)

    assert status["parse_status"] == "parsed_cover_page_checkbox_text"
    assert status["status_booleans"]["large_accelerated_filer"] is True
    assert status["status_booleans"]["accelerated_filer"] is False
    assert status["status_booleans"]["non_accelerated_filer"] is False
    assert status["status_booleans"]["smaller_reporting_company"] is False
    assert status["status_booleans"]["emerging_growth_company"] is False
    assert status["status_booleans"]["shell_company"] is False
    assert status["status_field_count"] == 6
    diagnostics = status["checkbox_diagnostics"]
    assert diagnostics["column_layout_fields"] == [
        "large_accelerated_filer",
        "accelerated_filer",
        "non_accelerated_filer",
        "smaller_reporting_company",
        "emerging_growth_company",
    ]
    assert diagnostics["shell_yes_no_parsed"] is True


def test_default_form_scope_admits_periodic_reports_without_8k_item_codes() -> None:
    forms = {form.upper().replace("/A", "") for form in text_backfill.DEFAULT_FORMS}
    item_codes = {"2.02"}

    assert text_backfill._event_matches(
        {"form_type": "6-K", "form_base": "6-K", "eight_k_item_codes": []},
        forms,
        item_codes,
    )
    assert text_backfill._event_matches(
        {"form_type": "10-K", "form_base": "10-K", "eight_k_item_codes": []},
        forms,
        item_codes,
    )
    assert text_backfill._event_matches(
        {"form_type": "10-Q", "form_base": "10-Q", "eight_k_item_codes": []},
        forms,
        item_codes,
    )
    assert text_backfill._event_matches(
        {"form_type": "8-K", "form_base": "8-K", "eight_k_item_codes": ["2.02"]},
        forms,
        item_codes,
    )
    assert not text_backfill._event_matches(
        {"form_type": "8-K", "form_base": "8-K", "eight_k_item_codes": ["5.02"]},
        forms,
        item_codes,
    )


def test_build_rows_summary_tracks_periodic_selection(tmp_path, monkeypatch) -> None:
    events_path = tmp_path / "events.jsonl"
    events = [
        {"ticker": "AAA", "form_type": "8-K", "form_base": "8-K", "accession_number": "1"},
        {"ticker": "BBB", "form_type": "6-K", "form_base": "6-K", "accession_number": "2"},
        {"ticker": "CCC", "form_type": "10-K", "form_base": "10-K", "accession_number": "3"},
        {"ticker": "DDD", "form_type": "10-Q", "form_base": "10-Q", "accession_number": "4"},
    ]
    events_path.write_text(
        "\n".join(json.dumps(row) for row in events) + "\n",
        encoding="utf-8",
    )

    def fake_fetch(event, **_kwargs):
        return {
            "status": "dry_run",
            "ticker": event.get("ticker"),
            "accession_number": event.get("accession_number"),
            "form_type": event.get("form_type"),
            "form_base": event.get("form_base"),
            "documents_fetched": 0,
            "text_char_count": 0,
            "combined_text": "",
        }

    monkeypatch.setattr(text_backfill, "fetch_filing_text", fake_fetch)
    args = argparse.Namespace(
        events=str(events_path),
        cache_dir=str(tmp_path / "cache"),
        forms=list(text_backfill.DEFAULT_FORMS),
        item_codes=["all"],
        limit=None,
        user_agent="test",
        max_documents=1,
        max_chars_per_doc=100,
        refresh=False,
        request_delay_sec=0.0,
    )

    rows, summary = text_backfill.build_rows(args)

    assert len(rows) == 4
    assert summary["source_events_input"] == 4
    assert summary["matched_events_input"] == 4
    assert summary["source_form_counts"]["10-K"] == 1
    assert summary["source_form_counts"]["10-Q"] == 1
    assert summary["selected_form_counts"]["10-K"] == 1
    assert summary["selected_form_counts"]["10-Q"] == 1
    assert summary["selected_periodic_rows"] == 2


def test_fetch_filing_text_attaches_dei_cover_status(tmp_path, monkeypatch) -> None:
    index_payload = {
        "directory": {
            "item": [
                {"name": "acme-20260630.htm"},
                {"name": "acme-20260630_htm.xml"},
            ]
        }
    }
    raw_documents = {
        "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/acme-20260630.htm": (
            "<html><body>10-Q cover page</body></html>"
        ),
        "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/acme-20260630_htm.xml": (
            "<dei:EntityFilerCategory>Non-accelerated Filer</dei:EntityFilerCategory>"
            "<dei:EntityEmergingGrowthCompany>true</dei:EntityEmergingGrowthCompany>"
        ),
    }

    monkeypatch.setattr(text_backfill, "request_json", lambda *_args, **_kwargs: index_payload)
    monkeypatch.setattr(text_backfill, "request_text", lambda url, *_args, **_kwargs: raw_documents[url])
    monkeypatch.setattr(text_backfill.time, "sleep", lambda *_args, **_kwargs: None)

    payload = text_backfill.fetch_filing_text(
        {
            "ticker": "ACME",
            "cik": "0000000001",
            "accession_number": "0000000001-26-000001",
            "form_type": "10-Q",
            "form_base": "10-Q",
            "primary_document": "acme-20260630.htm",
        },
        cache_dir=tmp_path,
        user_agent="test",
        max_documents=2,
        max_chars_per_doc=10000,
        request_delay_sec=0.0,
    )

    status = payload["dei_cover_status"]
    assert status["parse_status"] == "parsed_machine_readable_dei_fact"
    assert status["filer_category"] == "non_accelerated_filer"
    assert status["status_booleans"]["non_accelerated_filer"] is True
    assert status["status_booleans"]["emerging_growth_company"] is True
