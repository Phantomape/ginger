from __future__ import annotations

import sec_offering_economics_backfill as backfill


def test_select_rows_is_deterministic_and_prefers_unique_tickers() -> None:
    rows = [
        {
            "accession": f"0000000001-24-00000{index}",
            "ticker": ticker,
            "ticker_status": "resolved",
            "form_type": "S-1",
            "filed_date": "2024-10-03",
        }
        for index, ticker in enumerate(("AAA", "AAA", "BBB", "CCC", "DDD"), start=1)
    ]

    first = backfill.select_rows(rows, 3)
    second = backfill.select_rows(list(reversed(rows)), 3)

    assert [row["accession"] for row in first] == [row["accession"] for row in second]
    assert len({row["ticker"] for row in first}) == 3


def test_parse_filing_index_selects_exact_form_and_accepted_time() -> None:
    html = """
    <div class="infoHead">Accepted</div><div class="info">2024-10-02 16:51:02</div>
    <table>
      <tr><td>1</td><td>FORM F-1/A</td><td><a href="/Archives/main.htm">main</a></td><td>F-1/A</td><td>100</td></tr>
      <tr><td>2</td><td>EXHIBIT</td><td><a href="/Archives/ex.htm">ex</a></td><td>EX-99</td><td>10</td></tr>
    </table>
    """

    parsed = backfill.parse_filing_index(html, "F-1/A")

    assert parsed["primary_href"] == "/Archives/main.htm"
    assert parsed["accepted_at_sec_display"] == "2024-10-02T20:51:02Z"


def test_primary_document_url_unwraps_inline_xbrl_viewer() -> None:
    assert backfill.primary_document_url(
        "/ix?doc=/Archives/edgar/data/1/2/main.htm"
    ) == "https://www.sec.gov/Archives/edgar/data/1/2/main.htm"


def test_extract_offering_economics_classifies_mixed_and_amount() -> None:
    html = """
    <html><body>
      <p>We are offering shares of common stock under this prospectus.</p>
      <p>The selling stockholders may offer and sell additional shares.</p>
      <p>The proposed maximum aggregate offering price is $125 million.</p>
    </body></html>
    """

    parsed = backfill.extract_offering_economics(html)

    assert parsed["resale_vs_primary"] == "mixed_primary_and_resale"
    assert parsed["selling_holder_present"] is True
    assert parsed["registered_or_offering_amount_usd"] == 125_000_000
    assert parsed["resale_evidence"]["excerpt_sha256"]
    assert parsed["primary_evidence"]["excerpt_sha256"]


def test_extract_offering_economics_does_not_force_unknown_type() -> None:
    parsed = backfill.extract_offering_economics(
        "<html><body>Registration statement. No transaction terms here.</body></html>"
    )

    assert parsed["resale_vs_primary"] is None
    assert parsed["selling_holder_present"] is False
