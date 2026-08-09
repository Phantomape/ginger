from __future__ import annotations

import hashlib

from sec_cash_tender_lifecycle import (
    _attach_amendments_to_episodes,
    aggregate_episode_outcome,
    build_daily_default_off_candidate_snapshot,
    evaluate_locked_policy_eligibility,
    extract_amendment_outcome,
    extract_amendment_policy_delta,
    extract_subject_company,
    extract_filing_person_ciks,
    extract_target_event_outcome,
    extract_tender_terms,
    find_tender_document_links,
    normalize_html_text,
    parse_master_index,
    parse_sc_to_t_filing,
)


ACCESSION = "0000000001-25-000001"
RAW_URL = "https://www.sec.gov/Archives/edgar/data/1/0000000001-25-000001.txt"
PRIMARY_URL = "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/sctot.htm"
OFFER_URL = "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/offer.htm"


OFFER_HTML = """
<html>
  <head><title>Offer to Purchase for Cash</title></head>
  <body>
    <center>
      <b>Offer to Purchase for Cash<br>
      All Outstanding Shares of Common Stock of Target Systems, Inc.<br>
      at $17.50 Net Per Share</b>
    </center>
    <p>The common stock has a par value of $0.001 per share and is listed on
       the Nasdaq Global Select Market under the symbol "TGTX".</p>
    <p>The Offer is scheduled to expire at 11:59 p.m., New York City time,
       on February 14, 2025, unless extended.</p>
    <p>The board of directors unanimously recommends that stockholders accept
       the Offer and tender their Shares.</p>
    <p>Parent and Target entered into an Agreement and Plan of Merger, dated
       as of January 3, 2025.</p>
    <p>The Offer is not subject to any financing condition.</p>
    <p>Purchaser entered into an executed debt commitment letter under which
       the lenders have committed to provide funds sufficient to purchase all
       Shares validly tendered.</p>
  </body>
</html>
"""


RAW_SUBMISSION = f"""
<SEC-DOCUMENT>{ACCESSION}.txt : 20250106
<SEC-HEADER>
<ACCEPTANCE-DATETIME>20250106173122
SUBJECT COMPANY:
    COMPANY DATA:
        COMPANY CONFORMED NAME: TARGET SYSTEMS, INC.
        CENTRAL INDEX KEY: 0000000002
    BUSINESS ADDRESS:
        CITY: NEW YORK
FILED BY:
    COMPANY DATA:
        COMPANY CONFORMED NAME: BUYER ACQUISITION CORP.
        CENTRAL INDEX KEY: 0000000001
</SEC-HEADER>
<DOCUMENT>
<TYPE>SC TO-T
<SEQUENCE>1
<FILENAME>sctot.htm
<DESCRIPTION>Schedule TO Tender Offer Statement
<TEXT><html><body><p>Items incorporated by reference from the Offer to Purchase.</p></body></html></TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>EX-99.(A)(1)(A)
<SEQUENCE>2
<FILENAME>offer.htm
<DESCRIPTION>Offer to Purchase
<TEXT>{OFFER_HTML}</TEXT>
</DOCUMENT>
"""


def _index_row() -> dict:
    return {
        "accession_number": ACCESSION,
        "form_type": "SC TO-T",
        "filing_date": "2025-01-06",
        "raw_submission_url": RAW_URL,
    }


def _fetcher(payloads: dict[str, str | bytes]):
    def fetch(url: str):
        return payloads[url]

    return fetch


def _security_context() -> dict:
    return {
        "ticker": "TGTX",
        "is_listed_common_stock": True,
        "is_otc": False,
        "is_bankrupt": False,
    }


def _parsed_episode() -> dict:
    return parse_sc_to_t_filing(
        _index_row(),
        fetcher=_fetcher({RAW_URL: RAW_SUBMISSION}),
    )


def test_master_index_dedupes_paired_filer_subject_rows_by_accession():
    master = f"""Description: Master Index of EDGAR Dissemination Feed
CIK|Company Name|Form Type|Date Filed|Filename
--------------------------------------------------------------------------------
1|Buyer Acquisition Corp|SC TO-T|2025-01-06|edgar/data/1/{ACCESSION}.txt
2|Target Systems Inc|SC TO-T|2025-01-06|edgar/data/1/{ACCESSION}.txt
3|Other Target|SC TO-T/A|2025-01-07|edgar/data/3/0000000003-25-000002.txt
4|Not Relevant|8-K|2025-01-08|edgar/data/4/0000000004-25-000003.txt
"""

    rows = parse_master_index(master, source_url="memory://master.idx")

    assert len(rows) == 2
    initial = rows[0]
    assert initial["accession_number"] == ACCESSION
    assert initial["duplicate_index_row_count"] == 1
    assert initial["index_ciks"] == ["0000000001", "0000000002"]
    assert initial["master_index_sha256"] == hashlib.sha256(master.encode()).hexdigest()


def test_subject_identity_and_document_links_come_from_target_header_and_sgml():
    subject = extract_subject_company(RAW_SUBMISSION)
    links = find_tender_document_links(
        RAW_SUBMISSION,
        raw_submission_url=RAW_URL,
        accession_number=ACCESSION,
    )

    assert subject == {
        "subject_company_name": "TARGET SYSTEMS, INC.",
        "subject_cik": "0000000002",
        "accepted_at": "2025-01-06T17:31:22",
        "accepted_at_raw": "20250106173122",
        "subject_header_found": True,
    }
    assert extract_filing_person_ciks(RAW_SUBMISSION) == ["0000000001"]
    assert links["primary_schedule_to"]["source_url"] == PRIMARY_URL
    assert links["offer_to_purchase_exhibit"]["source_url"] == OFFER_URL


def test_standard_a1i_exhibit_is_offer_to_purchase_without_helpful_description():
    lbph_offer = """
    <html><body>
      <center>Offer to Purchase for Cash<br>All Outstanding Shares of Common
      Stock of Longboard Pharmaceuticals, Inc.<br>at $60.00 Per Share</center>
      <p>The Shares are listed on the Nasdaq Global Market under the symbol “LBPH”.</p>
      <p>The Offer will expire at one minute after 11:59 p.m., Eastern Time,
      on November 27, 2024, unless extended.</p>
      <p>The Board of Directors has unanimously resolved to recommend that the
      stockholders accept the Offer and tender their Shares.</p>
      <p>The parties entered into an Agreement and Plan of Merger, dated as of
      October 13, 2024.</p>
      <p>The Offer is not subject to any financing condition.</p>
      <p>Parent has sufficient cash resources available to fund the Offer and
      purchase all Shares validly tendered.</p>
    </body></html>
    """
    raw = RAW_SUBMISSION.replace(
        "<TYPE>EX-99.(A)(1)(A)", "<TYPE>EX-99.(A)(1)(I)"
    ).replace(
        "<FILENAME>offer.htm\n<DESCRIPTION>Offer to Purchase",
        "<FILENAME>ny20037200x5_exa1i.htm\n<DESCRIPTION>EXHIBIT (A)(1)(I)",
    ).replace(OFFER_HTML, lbph_offer)
    links = find_tender_document_links(
        raw,
        raw_submission_url=RAW_URL,
        accession_number=ACCESSION,
    )
    episode = parse_sc_to_t_filing(
        _index_row(),
        fetcher=_fetcher({RAW_URL: raw}),
    )

    assert links["offer_to_purchase_exhibit"]["document_type"] == "EX-99.(A)(1)(I)"
    assert links["offer_to_purchase_exhibit"]["filename"] == "ny20037200x5_exa1i.htm"
    assert episode["terms"]["offer_price_usd"] == 60.0
    assert episode["terms"]["scheduled_expiration_date"] == "2024-11-27"
    assert episode["terms"]["target_board_recommends_tender"] is True
    assert episode["terms"]["no_financing_condition"] is True
    assert episode["terms"]["binding_committed_financing"] is True
    assert episode["terms"]["financing_evidence_kind"] == "cash_on_hand"
    assert episode["terms"]["target_ticker"] == "LBPH"
    assert episode["terms"]["target_exchange"] == "NASDAQ"
    assert episode["terms"]["bankruptcy_indicated"] is False
    assert episode["policy_eligible"] is True


def test_normalized_html_and_terms_extract_exact_cash_price_not_par_value():
    terms = extract_tender_terms(
        {
            "content": OFFER_HTML,
            "source_url": OFFER_URL,
            "role": "offer_to_purchase_exhibit",
        }
    )

    assert "Offer to Purchase for Cash" in normalize_html_text(OFFER_HTML)
    assert terms["offer_price_usd"] == 17.5
    assert terms["offer_price_usd"] != 0.001
    assert terms["offer_price_ambiguous"] is False
    assert terms["fixed_cash_offer"] is True
    assert terms["all_outstanding_shares"] is True
    assert terms["target_board_recommends_tender"] is True
    assert terms["definitive_agreement"] is True
    assert terms["no_financing_condition"] is True
    assert terms["binding_committed_financing"] is True
    assert terms["financing_evidence_kind"] == "binding_commitment"
    assert terms["scheduled_expiration_date"] == "2025-02-14"
    assert terms["agreement_or_announcement_date"] == "2025-01-03"
    assert terms["target_ticker"] == "TGTX"
    assert terms["target_exchange"] == "NASDAQ"
    assert terms["listed_common_stock_evidence"]["source_url"] == OFFER_URL
    price_evidence = [row for row in terms["evidence_spans"] if row["field"] == "offer_price_usd"]
    assert price_evidence
    assert all(row["source_url"] == OFFER_URL for row in price_evidence)
    assert all(len(row["source_sha256"]) == 64 for row in price_evidence)


def test_cvr_is_excluded_and_highly_confident_financing_fails_closed():
    html = OFFER_HTML.replace(
        "at $17.50 Net Per Share",
        "at $17.50 Net Per Share plus one contingent value right (CVR)",
    ).replace(
        "Purchaser entered into an executed debt commitment letter under which\n"
        "       the lenders have committed to provide funds sufficient to purchase all\n"
        "       Shares validly tendered.",
        "Purchaser has received a highly confident letter and expects to obtain financing.",
    )
    terms = extract_tender_terms(html, source_url="memory://cvr-offer.htm")

    assert terms["has_cvr_consideration"] is True
    assert terms["fixed_cash_offer"] is False
    assert terms["binding_committed_financing"] is False
    assert terms["financing_evidence_kind"] == "unclear"


def test_historical_proposal_and_merger_boilerplate_do_not_poison_current_cash_offer():
    html = OFFER_HTML.replace(
        "The common stock has a par value",
        "The Shares currently trade on Nasdaq under the symbol “TGTX”. "
        "The common stock has a par value",
    ) + """
    <p>An earlier proposal consisted of $15.00 cash plus a contingent value
       right of $2.00, but that historical proposal was rejected.</p>
    <p>An Acquisition Proposal includes any recapitalization, tender offer or
       exchange offer that would result in ownership of 15% or more.</p>
    <p>Purchaser may not decrease the maximum number of Shares sought to be
       purchased in the Offer.</p>
    """

    terms = extract_tender_terms(html, source_url="memory://real-style-offer.htm")

    assert terms["target_ticker"] == "TGTX"
    assert terms["target_exchange"] == "NASDAQ"
    assert terms["has_cvr_consideration"] is False
    assert terms["has_stock_consideration"] is False
    assert terms["is_partial_offer"] is False
    assert terms["fixed_cash_offer"] is True


def test_current_offer_heading_with_cvr_is_excluded_but_historical_cvr_stays_ignored():
    current = OFFER_HTML.replace(
        "at $17.50 Net Per Share",
        "at $17.50 per share, net in cash, plus one non-tradable "
        "contingent value right (CVR) per share",
    )
    historical = OFFER_HTML + """
    <p>An earlier non-binding proposal offered $15.00 per share in cash plus
       one contingent value right, but the board rejected that proposal.</p>
    """

    assert extract_tender_terms(current)["has_cvr_consideration"] is True
    assert extract_tender_terms(current)["fixed_cash_offer"] is False
    assert extract_tender_terms(historical)["has_cvr_consideration"] is False
    assert extract_tender_terms(historical)["fixed_cash_offer"] is True


def test_real_contract_wording_variants_preserve_strict_policy_evidence():
    html = OFFER_HTML.replace(
        "The board of directors unanimously recommends that stockholders accept\n"
        "       the Offer and tender their Shares.",
        "The board of directors of Target Systems (the Company Board) has unanimously "
        "determined the transaction is fair, approved the execution and delivery of "
        "the agreement, resolved that the merger be effected under Section 251(h), "
        "and recommended that the stockholders of Target Systems accept the Offer "
        "and tender their Shares.",
    ).replace(
        "Parent and Target entered into an Agreement and Plan of Merger, dated\n"
        "       as of January 3, 2025.",
        "The Offer is being made pursuant to the Purchase Agreement, dated as of "
        "January 3, 2025, by and among Parent, Purchaser and Target.",
    ).replace(
        "The Offer is not subject to any financing condition.",
        "The consummation of the Offer is not subject to, or contingent upon, "
        "any financing condition.",
    )

    terms = extract_tender_terms(html)

    assert terms["target_board_recommends_tender"] is True
    assert terms["definitive_agreement"] is True
    assert terms["agreement_or_announcement_date"] == "2025-01-03"
    assert terms["no_financing_condition"] is True


def test_named_target_board_recommendation_after_long_resolution_is_recognized():
    html = OFFER_HTML.replace(
        "The board of directors unanimously recommends that stockholders accept\n"
        "       the Offer and tender their Shares.",
        "After careful consideration, the GLDD Board has unanimously: "
        "(i) determined that the transaction is in the best interests of GLDD, "
        "(ii) approved the execution and delivery of the Merger Agreement and "
        "the consummation of the Transactions, (iii) resolved that the Merger "
        "shall be effected under Section 251(h), and (iv) recommended that GLDD "
        "Stockholders accept the Offer and tender their Shares to Purchaser.",
    )

    assert extract_tender_terms(html)["target_board_recommends_tender"] is True


def test_sufficient_cash_on_hand_is_valid_financing_evidence():
    html = OFFER_HTML.replace(
        "Purchaser entered into an executed debt commitment letter under which\n"
        "       the lenders have committed to provide funds sufficient to purchase all\n"
        "       Shares validly tendered.",
        "Purchaser has sufficient cash on hand available to purchase all Shares and pay all fees.",
    )
    terms = extract_tender_terms(html)

    assert terms["binding_committed_financing"] is True
    assert terms["financing_evidence_kind"] == "cash_on_hand"


def test_explicit_available_funds_including_cash_on_hand_is_valid_evidence():
    html = OFFER_HTML.replace(
        "Purchaser entered into an executed debt commitment letter under which\n"
        "       the lenders have committed to provide funds sufficient to purchase all\n"
        "       Shares validly tendered.",
        "Parent and Purchaser have or will have such funds available to them through "
        "a variety of sources, including cash on hand and borrowings, at the time "
        "required in connection with the Offer Closing.",
    )

    terms = extract_tender_terms(html)

    assert terms["binding_committed_financing"] is True
    assert terms["financing_evidence_kind"] == "cash_on_hand"


def test_parse_filing_preserves_hashes_and_infers_locked_identity_from_offer_text():
    episode = _parsed_episode()

    assert episode["subject_cik"] == "0000000002"
    assert episode["terms"]["offer_price_usd"] == 17.5
    assert episode["raw_submission_sha256"] == hashlib.sha256(RAW_SUBMISSION.encode()).hexdigest()
    assert episode["primary_schedule_to"]["used_embedded_content"] is True
    assert episode["primary_schedule_to"]["fetch_error"] is None
    # Ticker/listing/non-OTC and the deterministic bankruptcy screen are all
    # derived from the immutable offer-to-purchase text.
    assert episode["eligibility"]["ticker"] == "TGTX"
    assert episode["eligibility"]["eligible"] is True
    assert episode["eligibility"]["fail_closed_reasons"] == []

    eligible = evaluate_locked_policy_eligibility(episode, security_context=_security_context())
    assert eligible["document_policy_eligible"] is True
    assert eligible["market_identity_eligible"] is True
    assert eligible["eligible"] is True
    assert eligible["trade_enabled"] is False


def test_explicit_target_chapter_11_language_sets_bankruptcy_exclusion_with_evidence():
    terms = extract_tender_terms(
        OFFER_HTML.replace(
            "The Offer is not subject to any financing condition.",
            "The Target has filed a voluntary petition for relief under Chapter 11 bankruptcy. "
            "The Offer is not subject to any financing condition.",
        ),
        source_url="memory://bankrupt-target.htm",
    )

    assert terms["bankruptcy_indicated"] is True
    assert terms["bankruptcy_evidence"]["source_url"] == "memory://bankrupt-target.htm"


def test_completion_and_termination_outcomes_require_explicit_language():
    completed = extract_amendment_outcome(
        """
        <p>The Offer expired at midnight on February 14, 2025.</p>
        <p>Purchaser accepted for payment all Shares validly tendered pursuant to the Offer.</p>
        """,
        source_url="memory://completed.htm",
    )
    higher = extract_amendment_outcome(
        """
        <p>The Company terminated the Merger Agreement in order to accept a
        Superior Proposal from Rival Holdings.</p>
        """,
        source_url="memory://higher.htm",
    )
    negative = extract_amendment_outcome(
        """
        <p>The parties terminated the Merger Agreement after the regulatory
        condition could not be satisfied. The Offer was withdrawn.</p>
        """,
        source_url="memory://terminated.htm",
    )

    assert completed["outcome_type"] == "completed"
    assert completed["completed"] is True
    assert completed["evidence_spans"][0]["source_url"] == "memory://completed.htm"
    assert higher["outcome_type"] == "terminated_higher_bid"
    assert higher["higher_bid_identified"] is True
    assert higher["higher_bidder_name"] == "Rival Holdings"
    assert negative["outcome_type"] == "terminated_negative"
    assert negative["higher_bid_identified"] is False


def test_real_final_amendment_acceptance_wording_is_completed():
    examples = (
        "Lilly and Purchaser have accepted for payment, and will promptly pay for, "
        "all Shares that were validly tendered and not validly withdrawn.",
        "Purchaser has irrevocably accepted for payment all such Shares validly "
        "tendered into and not validly withdrawn from the Offer.",
        "All conditions having been satisfied, Purchaser irrevocably accepted for "
        "payment, and will cause the Depositary to pay for, as promptly as practicable, "
        "all Shares validly tendered and not validly withdrawn.",
        "Promptly after expiration, Purchaser accepted all Shares validly tendered "
        "and not validly withdrawn and will promptly pay for all Shares accepted.",
    )

    assert all(extract_amendment_outcome(text)["outcome_type"] == "completed" for text in examples)


def test_target_8k_item_201_requires_matching_cash_price_and_past_acceptance():
    item_201 = """
    <h2>Item 2.01 Completion of Acquisition or Disposition of Assets</h2>
    <p>Merger Sub commenced a tender offer to acquire all outstanding shares
       of common stock at a purchase price of $11.30 per Share in cash.</p>
    <p>Promptly after the Expiration Time, Merger Sub accepted all Shares
       validly tendered and not validly withdrawn pursuant to the Offer.</p>
    <p>Parent completed the acquisition of the Company on June 25, 2025.</p>
    <h2>Item 3.01 Notice of Delisting</h2>
    """

    matched = extract_target_event_outcome(
        item_201,
        source_url="memory://target-8k.htm",
        expected_cash_price_usd=11.30,
    )
    wrong_price = extract_target_event_outcome(
        item_201,
        expected_cash_price_usd=12.00,
    )
    prospective = extract_target_event_outcome(
        item_201.replace(
            "Merger Sub accepted all Shares",
            "Merger Sub expects to accept all Shares",
        ).replace(
            "Parent completed the acquisition", "Parent expects to complete the acquisition"
        ),
        expected_cash_price_usd=11.30,
    )

    assert matched["outcome_type"] == "completed"
    assert matched["source_contract_passed"] is True
    assert matched["outcome_date"] == "2025-06-25"
    assert wrong_price["outcome_type"] == "pending"
    assert wrong_price["source_contract_passed"] is False
    assert prospective["outcome_type"] == "pending"


def test_amendment_policy_delta_makes_real_cvr_or_withdrawn_recommendation_reachable():
    delta = extract_amendment_policy_delta(
        """
        <h1>Offer to Purchase all outstanding shares at $17.50 per share in cash,
        plus one contingent value right (CVR) per share</h1>
        <p>The board of directors recommends that stockholders not tender and
        rejects the revised Offer.</p>
        """,
        source_url="memory://invalidating-amendment.htm",
    )
    neutral = extract_amendment_policy_delta(
        "This amendment extends the expiration date and makes no other change."
    )

    assert delta["invalidates_policy"] is True
    assert "cvr_consideration_added" in delta["invalidation_reasons"]
    assert "target_board_recommendation_withdrawn" in delta["invalidation_reasons"]
    assert delta["evidence_spans"]
    assert neutral["invalidates_policy"] is False


def test_expected_future_acceptance_does_not_fake_completion():
    outcome = extract_amendment_outcome(
        "Purchaser expects to promptly accept for payment on December 2 all Shares "
        "that were validly tendered and not validly withdrawn."
    )

    assert outcome["outcome_type"] == "pending"


def test_risk_factor_termination_language_does_not_fake_terminal_outcome():
    outcome = extract_amendment_outcome(
        "The occurrence of any event or circumstance that could give rise to "
        "the termination of the merger agreement or any failure to consummate "
        "the proposed transaction may adversely affect the company."
    )

    assert outcome["outcome_type"] == "pending"


def test_present_progressive_offer_termination_is_terminal():
    outcome = extract_amendment_outcome(
        "We are terminating the Offer concurrently with execution of the new "
        "Merger Agreement. No Shares were accepted for payment."
    )

    assert outcome["outcome_type"] == "terminated_negative"


def test_offeror_board_approval_does_not_fake_target_recommendation():
    terms = extract_tender_terms(
        "Our Board of Directors has approved this Offer and we would be prepared "
        "to enter into definitive agreements. Consummation is conditioned on the "
        "target entering into a definitive merger agreement with Purchaser."
    )

    assert terms["target_board_recommends_tender"] is None


def test_extension_stays_pending_and_daily_snapshot_never_enables_orders():
    extension = extract_amendment_outcome(
        "The Purchaser extended the expiration date of the tender offer until March 3, 2025."
    )
    snapshot = build_daily_default_off_candidate_snapshot(
        as_of="2025-01-06",
        episodes=[_parsed_episode()],
        security_context_by_cik={"0000000002": _security_context()},
    )

    assert extension["outcome_type"] == "extended_pending"
    assert snapshot["candidate_count"] == 1
    assert snapshot["eligible_candidate_count"] == 1
    assert snapshot["candidates"][0]["ticker"] == "TGTX"
    assert snapshot["candidates"][0]["policy_eligible"] is True
    assert snapshot["trade_enabled"] is False
    assert snapshot["orders"] == []


def test_aggregate_keeps_latest_terminal_and_tracks_revised_cash_price():
    amendments = [
        {
            "accession_number": "amend-price",
            "filing_date": "2025-02-01",
            "outcome": extract_amendment_outcome(
                "Purchaser increased the Offer Price to $20.00 per share."
            ),
        },
        {
            "accession_number": "amend-complete",
            "filing_date": "2025-02-10",
            "outcome": extract_amendment_outcome(
                "Purchaser accepted for payment all Shares validly tendered."
            ),
        },
        {
            "accession_number": "amend-admin",
            "filing_date": "2025-02-12",
            "outcome": extract_amendment_outcome(
                "This amendment updates an exhibit index and makes no other change."
            ),
        },
    ]

    outcome = aggregate_episode_outcome(amendments, initial_offer_price_usd=17.5)

    assert outcome["outcome_type"] == "completed"
    assert outcome["amendment_accession_number"] == "amend-complete"
    assert outcome["amendment_filing_date"] == "2025-02-10"
    assert outcome["outcome_date"] == "2025-02-10"
    assert outcome["higher_bid_price_usd"] == 20.0
    assert outcome["cash_price_usd"] == 20.0
    assert outcome["higher_bid_prices"][0]["accession_number"] == "amend-price"


def test_amendments_match_offeror_identity_not_merely_latest_target_offer():
    first = {
        "accession_number": "initial-a",
        "filing_date": "2025-01-01",
        "subject_cik": "0000000001",
        "index_ciks": ["0000000001", "0000000010"],
    }
    second = {
        "accession_number": "initial-b",
        "filing_date": "2025-01-10",
        "subject_cik": "0000000001",
        "index_ciks": ["0000000001", "0000000020"],
    }
    amendment_a = {
        "accession_number": "amend-a",
        "filing_date": "2025-01-15",
        "subject_cik": "0000000001",
        "index_ciks": ["0000000001", "0000000010"],
    }

    _attach_amendments_to_episodes([first, second], [amendment_a])

    assert [row["accession_number"] for row in first["amendments"]] == ["amend-a"]
    assert second["amendments"] == []
    assert first["amendments"][0]["association"]["mode"] == "offeror_cik_overlap"


def test_ambiguous_target_only_amendment_fails_closed_instead_of_cross_wiring():
    episodes = [
        {
            "accession_number": "initial-a",
            "filing_date": "2025-01-01",
            "subject_cik": "0000000001",
            "index_ciks": ["0000000001", "0000000010"],
        },
        {
            "accession_number": "initial-b",
            "filing_date": "2025-01-10",
            "subject_cik": "0000000001",
            "index_ciks": ["0000000001", "0000000020"],
        },
    ]
    ambiguous = {
        "accession_number": "amend-ambiguous",
        "filing_date": "2025-01-15",
        "subject_cik": "0000000001",
        "index_ciks": ["0000000001"],
    }

    _attach_amendments_to_episodes(episodes, [ambiguous])

    assert all(row["amendments"] == [] for row in episodes)
    assert episodes[-1]["unassociated_target_amendments"][0]["accession_number"] == "amend-ambiguous"
    assert episodes[-1]["amendment_association_ambiguous"] is True
