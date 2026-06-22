from __future__ import annotations

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


def test_default_form_scope_admits_6k_without_8k_item_codes() -> None:
    forms = {form.upper().replace("/A", "") for form in text_backfill.DEFAULT_FORMS}
    item_codes = {"2.02"}

    assert text_backfill._event_matches(
        {"form_type": "6-K", "form_base": "6-K", "eight_k_item_codes": []},
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
