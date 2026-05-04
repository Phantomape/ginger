from __future__ import annotations

from datetime import date

from form4_backfill import (
    archive_url,
    conservative_usable_trade_date,
    iter_recent_form4_filings,
    parse_form4_xml,
    raw_form4_archive_url,
    raw_form4_primary_document,
)


def test_iter_recent_form4_filings_filters_window_and_builds_archive_url():
    payload = {
        "cik": "320193",
        "filings": {
            "recent": {
                "form": ["10-K", "4", "4/A"],
                "filingDate": ["2025-01-01", "2025-05-02", "2026-01-01"],
                "acceptanceDateTime": ["20250101120000", "20250502170100", "20260101120000"],
                "accessionNumber": ["0001", "0000320193-25-000111", "0003"],
                "primaryDocument": ["a.htm", "primary_doc.xml", "c.xml"],
                "reportDate": ["2024-12-31", "2025-05-01", "2025-12-31"],
            }
        },
    }

    rows = iter_recent_form4_filings(
        payload,
        ticker="AAPL",
        cik="320193",
        start=date(2025, 1, 1),
        end=date(2025, 12, 31),
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["filing_type"] == "4"
    assert rows[0]["accepted_at"] == "2025-05-02T17:01:00"
    assert rows[0]["usable_trade_date"] == "2025-05-05"
    assert rows[0]["archive_url"] == archive_url("0000320193", "0000320193-25-000111", "primary_doc.xml")


def test_parse_form4_xml_extracts_open_market_purchase_fields():
    xml = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <periodOfReport>2025-05-01</periodOfReport>
  <issuer>
    <issuerCik>0000320193</issuerCik>
    <issuerName>Apple Inc.</issuerName>
    <issuerTradingSymbol>AAPL</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0001111111</rptOwnerCik>
      <rptOwnerName>Example CEO</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>1</isDirector>
      <isOfficer>1</isOfficer>
      <isTenPercentOwner>0</isTenPercentOwner>
      <isOther>0</isOther>
      <officerTitle>Chief Executive Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2025-05-01</value></transactionDate>
      <transactionCoding>
        <transactionFormType>4</transactionFormType>
        <transactionCode>P</transactionCode>
        <equitySwapInvolved>0</equitySwapInvolved>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1000</value></transactionShares>
        <transactionPricePerShare><value>12.50</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>5000</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
      <ownershipNature>
        <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
      </ownershipNature>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  <remarks>Open-market purchase.</remarks>
</ownershipDocument>
"""
    filing = {
        "ticker": "AAPL",
        "cik": "0000320193",
        "filing_type": "4",
        "filing_date": "2025-05-02",
        "accepted_at": "2025-05-02T17:01:00",
        "accession_number": "0000320193-25-000111",
        "primary_document": "primary_doc.xml",
    }

    rows = parse_form4_xml(xml, filing)

    assert len(rows) == 1
    row = rows[0]
    assert row["ticker"] == "AAPL"
    assert row["owner_name"] == "Example CEO"
    assert row["is_director"] is True
    assert row["is_officer"] is True
    assert row["officer_title"] == "Chief Executive Officer"
    assert row["transaction_code"] == "P"
    assert row["shares"] == 1000
    assert row["price"] == 12.5
    assert row["transaction_value"] == 12500
    assert row["open_market_purchase_flag"] is True
    assert row["option_exercise_flag"] is False
    assert row["pit_safe_flag"] is True
    assert row["usable_trade_date"] == "2025-05-05"


def test_parse_form4_xml_prefers_xml_issuer_over_submission_filer():
    xml = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <issuer>
    <issuerCik>0002222222</issuerCik>
    <issuerName>Issuer Corp</issuerName>
    <issuerTradingSymbol>ISSR</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0001111111</rptOwnerCik>
      <rptOwnerName>Owner Corp</rptOwnerName>
    </reportingOwnerId>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1</value></transactionShares>
        <transactionPricePerShare><value>2</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""
    rows = parse_form4_xml(xml, {"ticker": "OWNR", "cik": "0001111111"})

    assert rows[0]["ticker"] == "ISSR"
    assert rows[0]["cik"] == "0002222222"
    assert rows[0]["submission_ticker"] == "OWNR"
    assert rows[0]["submission_cik"] == "0001111111"


def test_conservative_usable_trade_date_uses_next_weekday_after_filing():
    assert conservative_usable_trade_date(None, "2025-05-02") == "2025-05-05"


def test_raw_form4_archive_url_drops_xsl_rendering_prefix():
    assert raw_form4_primary_document("xslF345X05/wk-form4_1730840851.xml") == "wk-form4_1730840851.xml"
    assert raw_form4_archive_url(
        "0000002488",
        "0000002488-24-000165",
        "xslF345X05/wk-form4_1730840851.xml",
    ) == (
        "https://www.sec.gov/Archives/edgar/data/"
        "2488/000000248824000165/wk-form4_1730840851.xml"
    )
