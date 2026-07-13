"""Tests for quant.sec_13d13g_ingest parser (exp-20260618-016).

Covers both EDGAR structured schemas: schedule13G (classPercent /
reportingPersonBeneficiallyOwnedAggregateNumberOfShares /
eventDateRequiresFilingThisStatement) and schedule13D (percentOfClass /
aggregateAmountOwned / dateOfEvent). No network access.
"""

from __future__ import annotations

from quant import sec_13d13g_ingest as ingest

XML_13G = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13g" xmlns:com="http://www.sec.gov/edgar/common">
  <headerData><submissionType>SCHEDULE 13G/A</submissionType></headerData>
  <formData>
    <coverPageHeader>
      <amendmentNo>3</amendmentNo>
      <eventDateRequiresFilingThisStatement>12/31/2025</eventDateRequiresFilingThisStatement>
      <issuerInfo>
        <issuerCik>0000001800</issuerCik>
        <issuerName>Abbott Laboratories</issuerName>
        <issuerCusips><issuerCusipNumber>002824100</issuerCusipNumber></issuerCusips>
      </issuerInfo>
    </coverPageHeader>
    <coverPageHeaderReportingPersonDetails>
      <reportingPersonName>The Vanguard Group</reportingPersonName>
      <reportingPersonBeneficiallyOwnedAggregateNumberOfShares>120000000</reportingPersonBeneficiallyOwnedAggregateNumberOfShares>
      <classPercent>8.4</classPercent>
      <typeOfReportingPerson>IA</typeOfReportingPerson>
    </coverPageHeaderReportingPersonDetails>
  </formData>
</edgarSubmission>"""

XML_13D = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13D" xmlns:com="http://www.sec.gov/edgar/common">
  <headerData><submissionType>SCHEDULE 13D</submissionType></headerData>
  <formData>
    <coverPageHeader>
      <dateOfEvent>03/24/2025</dateOfEvent>
      <issuerName>Acme Corp</issuerName>
    </coverPageHeader>
    <reportingPersons>
      <reportingPersonInfo>
        <reportingPersonName>Activist Capital LP</reportingPersonName>
        <aggregateAmountOwned>15855875.00</aggregateAmountOwned>
        <percentOfClass>5.6</percentOfClass>
        <typeOfReportingPerson>PN</typeOfReportingPerson>
      </reportingPersonInfo>
      <reportingPersonInfo>
        <reportingPersonName>Jane Founder</reportingPersonName>
        <aggregateAmountOwned>30000000.00</aggregateAmountOwned>
        <percentOfClass>11.2</percentOfClass>
        <typeOfReportingPerson>IN</typeOfReportingPerson>
      </reportingPersonInfo>
    </reportingPersons>
  </formData>
</edgarSubmission>"""

XML_13D_ITEM4_GOVERNANCE = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13D">
  <headerData><submissionType>SCHEDULE 13D/A</submissionType></headerData>
  <formData>
    <coverPageHeader>
      <dateOfEvent>02/18/2026</dateOfEvent>
      <issuerName>Example Software Inc.</issuerName>
    </coverPageHeader>
    <reportingPersons>
      <reportingPersonInfo>
        <reportingPersonName>Activist Fund LP</reportingPersonName>
        <aggregateAmountOwned>9000000</aggregateAmountOwned>
        <percentOfClass>6.7</percentOfClass>
        <typeOfReportingPerson>IA</typeOfReportingPerson>
      </reportingPersonInfo>
    </reportingPersons>
    <items>
      <item4>
        On February 18, 2026, the Reporting Persons entered into a cooperation
        agreement with the Issuer. Pursuant to the cooperation agreement, the
        Issuer agreed to appoint one independent director, appoint a second
        independent director before the 2026 annual meeting, and accept the
        resignation of a current director. The Reporting Persons withdrew their
        nomination of one director nominee and agreed to a customary standstill
        for 18 months.
      </item4>
    </items>
  </formData>
</edgarSubmission>"""


def test_parse_13g_classpercent_and_holder():
    parsed = ingest.parse_schedule_xml(XML_13G)
    assert parsed is not None
    assert parsed["submission_type"] == "SCHEDULE 13G/A"
    assert parsed["issuer_name"] == "Abbott Laboratories"
    assert parsed["event_date"] == "12/31/2025"
    assert len(parsed["reporting_persons"]) == 1
    person = parsed["reporting_persons"][0]
    assert person["reporting_person_name"] == "The Vanguard Group"
    assert person["class_percent"] == 8.4
    assert person["aggregate_shares"] == 120000000.0
    assert person["reporting_person_type"] == "IA"
    flags = ingest._holder_flags(parsed["reporting_persons"])
    assert flags["is_big3"] is True
    assert flags["max_class_percent"] == 8.4


def test_parse_13d_percentofclass_multi_person():
    parsed = ingest.parse_schedule_xml(XML_13D)
    assert parsed is not None
    assert parsed["submission_type"] == "SCHEDULE 13D"
    assert parsed["event_date"] == "03/24/2025"
    assert len(parsed["reporting_persons"]) == 2
    pcts = sorted(p["class_percent"] for p in parsed["reporting_persons"])
    assert pcts == [5.6, 11.2]
    flags = ingest._holder_flags(parsed["reporting_persons"])
    assert flags["is_big3"] is False
    assert flags["max_class_percent"] == 11.2
    assert set(flags["reporting_person_types"]) == {"PN", "IN"}


def test_extract_item4_governance_terms():
    item4 = ingest.extract_item4_text(XML_13D_ITEM4_GOVERNANCE)
    assert item4 is not None
    terms = ingest.classify_item4_governance_terms(item4, filing_date="2026-02-18")
    assert terms["governance_terms_present"] is True
    assert terms["governance_terms_bucket"] == "board_seat_and_standstill"
    assert terms["cooperation_or_settlement_agreement_present"] is True
    assert terms["board_terms_present"] is True
    assert terms["board_appointment_count"] == 2
    assert terms["nomination_withdrawal_present"] is True
    assert terms["board_departure_present"] is True
    assert terms["standstill_terms_present"] is True
    assert terms["standstill_duration_days"] == 540
    assert "board_appointment_count" in terms["governance_term_hits"]


def test_governance_terms_capture_board_member_appointment_without_support_noise():
    text = (
        "The Issuer entered into a voting and support agreement related to a "
        "merger. Separately, the investor entered into a cooperation agreement "
        "and Edward Garden was appointed as a member of the Board."
    )
    terms = ingest.classify_item4_governance_terms(text, filing_date="2026-01-06")
    assert terms["cooperation_or_settlement_agreement_present"] is True
    assert terms["board_terms_present"] is True
    assert terms["board_appointment_count"] == 1
    support_only = ingest.classify_item4_governance_terms(
        "The parties entered into a voting and support agreement for a merger."
    )
    assert support_only["cooperation_or_settlement_agreement_present"] is False
    assert support_only["governance_terms_present"] is False


def test_build_parsed_rows_exposes_governance_terms(monkeypatch, tmp_path):
    accession = "0000000000-26-000001"
    cache = tmp_path / f"{accession.replace('-', '')}.xml"
    cache.write_text(XML_13D_ITEM4_GOVERNANCE, encoding="utf-8")
    monkeypatch.setattr(ingest, "XML_CACHE_DIR", tmp_path)
    result = ingest.build_parsed_rows(
        [
            {
                "ticker": "EXM",
                "issuer_cik": "0000000000",
                "accession_number": accession,
                "form": "SCHEDULE 13D/A",
                "family": "13D",
                "is_amendment": True,
                "primary_doc_description": "SCHEDULE 13D/A",
                "filing_date": "2026-02-18",
                "accepted_at": "2026-02-18T21:00:00.000Z",
                "primary_document": "primary_doc.xml",
                "structured_xml": True,
                "window": "late_strong",
                "usable_trade_date": "2026-02-19",
            }
        ],
        fetch=False,
        refresh=False,
    )
    assert result["fetch_status"] == {"cached": 1}
    row = result["rows"][0]
    assert row["item4_text_present"] is True
    assert row["item4_governance_terms_present"] is True
    assert row["item4_governance_terms_bucket"] == "board_seat_and_standstill"
    assert row["item4_board_appointment_count"] == 2
    assert row["item4_standstill_duration_days"] == 540


def test_parse_rejects_non_structured():
    assert ingest.parse_schedule_xml("<html><body>not edgar</body></html>") is None
    assert ingest.extract_item4_text("<html><body>not edgar</body></html>") is None


def test_to_float_filters_junk():
    assert ingest._to_float("See Items 11 and 13") is None
    assert ingest._to_float("5.6") == 5.6
    assert ingest._to_float("1,234.5") == 1234.5


def test_family_and_amendment_detection():
    assert ingest.is_13d13g("SCHEDULE 13D/A", "") == (True, "13D", True)
    assert ingest.is_13d13g("SCHEDULE 13G", "") == (True, "13G", False)
    assert ingest.is_13d13g("8-K", "") == (False, None, False)


def test_next_business_day_skips_weekend():
    # 2025-03-21 is a Friday -> next business day is Monday 2025-03-24.
    assert ingest._next_business_day("2025-03-21") == "2025-03-24"


# 13G/A amendment carrying the authoritative current stake in item4 plus the
# previousAccessionNumber chain and the drop-below-5% exit flag (exp-014).
XML_13GA_EXIT = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13g">
  <headerData>
    <submissionType>SCHEDULE 13G/A</submissionType>
    <previousAccessionNumber>0000861177-23-000002</previousAccessionNumber>
  </headerData>
  <formData>
    <coverPageHeader>
      <amendmentNo>2</amendmentNo>
      <issuerInfo><issuerName>SLM Corp</issuerName></issuerInfo>
    </coverPageHeader>
    <coverPageHeaderReportingPersonDetails>
      <reportingPersonName>The Vanguard Group</reportingPersonName>
      <typeOfReportingPerson>IA</typeOfReportingPerson>
    </coverPageHeaderReportingPersonDetails>
    <items>
      <item4>
        <amountBeneficiallyOwned>0</amountBeneficiallyOwned>
        <classPercent>0</classPercent>
      </item4>
      <item5><classOwnership5PercentOrLess>Y</classOwnership5PercentOrLess></item5>
    </items>
  </formData>
</edgarSubmission>"""

# 13G/A amendment where the holder INCREASED to a numeric item4 percent and is
# still above 5%.
XML_13GA_INCREASE = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13g">
  <headerData>
    <submissionType>SCHEDULE 13G/A</submissionType>
    <previousAccessionNumber>0001111111-24-000010</previousAccessionNumber>
  </headerData>
  <formData>
    <coverPageHeaderReportingPersonDetails>
      <reportingPersonName>Boutique Partners LP</reportingPersonName>
      <typeOfReportingPerson>IA</typeOfReportingPerson>
    </coverPageHeaderReportingPersonDetails>
    <items>
      <item4>
        <amountBeneficiallyOwned>9000000</amountBeneficiallyOwned>
        <classPercent>9.3</classPercent>
      </item4>
      <item5><classOwnership5PercentOrLess>N</classOwnership5PercentOrLess></item5>
    </items>
  </formData>
</edgarSubmission>"""


def test_direction_fields_exit_below5():
    d = ingest.parse_13ga_direction_fields(XML_13GA_EXIT)
    assert d is not None
    assert d["previous_accession"] == "0000861177-23-000002"
    assert d["below_5pct"] is True
    assert d["item4_current_max_percent"] == 0.0
    assert d["item4_current_max_shares"] == 0.0
    assert d["item4_person_count"] == 1


def test_direction_fields_increase_above5():
    d = ingest.parse_13ga_direction_fields(XML_13GA_INCREASE)
    assert d is not None
    assert d["previous_accession"] == "0001111111-24-000010"
    assert d["below_5pct"] is False
    assert d["item4_current_max_percent"] == 9.3


def test_build_parsed_rows_computes_13ga_stake_change_direction(monkeypatch, tmp_path):
    previous_accession = "0001111111-24-000010"
    current_accession = "0001111111-25-000020"
    (tmp_path / f"{previous_accession.replace('-', '')}.xml").write_text(
        XML_13G, encoding="utf-8"
    )
    (tmp_path / f"{current_accession.replace('-', '')}.xml").write_text(
        XML_13GA_INCREASE, encoding="utf-8"
    )
    monkeypatch.setattr(ingest, "XML_CACHE_DIR", tmp_path)
    base_event = {
        "ticker": "EXM",
        "issuer_cik": "0000000000",
        "primary_doc_description": "SCHEDULE 13G",
        "filing_date": "2025-01-02",
        "accepted_at": "2025-01-02T21:00:00.000Z",
        "primary_document": "primary_doc.xml",
        "structured_xml": True,
        "window": "mid_weak",
        "usable_trade_date": "2025-01-03",
        "family": "13G",
    }
    result = ingest.build_parsed_rows(
        [
            {
                **base_event,
                "accession_number": previous_accession,
                "form": "SCHEDULE 13G",
                "is_amendment": False,
            },
            {
                **base_event,
                "accession_number": current_accession,
                "form": "SCHEDULE 13G/A",
                "is_amendment": True,
            },
        ],
        fetch=False,
        refresh=False,
    )
    by_accession = {row["accession_number"]: row for row in result["rows"]}
    amended = by_accession[current_accession]
    assert amended["sec13ga_previous_accession"] == previous_accession
    assert amended["sec13ga_current_max_percent"] == 9.3
    assert amended["sec13ga_previous_max_percent"] == 8.4
    assert amended["sec13ga_percent_delta"] == 0.9
    assert amended["sec13ga_stake_change_direction"] == "increase"
    assert amended["sec13ga_direction_status"] == "computed"


def test_direction_fields_reject_non_structured():
    assert ingest.parse_13ga_direction_fields("<html>nope</html>") is None
