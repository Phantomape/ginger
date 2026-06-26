from __future__ import annotations

import argparse
import json

import sec_filing_text_backfill as text_backfill
from sec_filing_text_backfill import candidate_documents, html_to_text, normalize_text


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


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  a\n\n b\t c  ") == "a b c"


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
