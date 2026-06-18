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


def test_parse_rejects_non_structured():
    assert ingest.parse_schedule_xml("<html><body>not edgar</body></html>") is None


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
