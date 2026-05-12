from __future__ import annotations

from pathlib import Path

from sec_event_queue import (
    FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
    GOVERNANCE_QUEUE_NAME,
    FINANCIAL_REPORT_T1_QUEUE_NAME,
    LEADERSHIP_QUEUE_NAME,
    QUEUE_NAME,
    build_forward_financial_report_t1_queue_from_sec_filing_events,
    build_sec_governance_procedural_queue,
    build_forward_leadership_queue_from_sec_filing_text,
    build_forward_queue_from_sec_filing_text,
    build_sec_financial_report_t1_queue,
    build_sec_leadership_change_queue,
    build_sec_event_queue,
    governance_reaction_bucket,
    governance_semantic_subcategory,
    leadership_semantic_subcategory,
    language_features,
    load_sec_filing_text_rows,
    qualifies_sec_financial_report_t1_event,
    qualifies_sec_governance_procedural_event,
    qualifies_sec_leadership_change_event,
    qualifies_sec_negative_reaction_event,
)


def _row(**overrides):
    row = {
        "status": "ok",
        "ticker": "LITE",
        "cohort": "other_equity",
        "accession_number": "0001",
        "form_type": "8-K",
        "filing_date": "2026-05-04",
        "usable_trade_date": "2026-05-04",
        "accepted_at": "2026-05-04T16:30:00",
        "eight_k_item_codes": ["2.02", "9.01"],
        "primary_document": "lite-20260504.htm",
        "index_url": "https://www.sec.gov/example",
        "combined_text": (
            "Quarterly results showed revenue, net income and earnings per share. "
            "Management discussed headwinds, margin pressure and weak demand."
        ),
    }
    row.update(overrides)
    return row


def _ohlcv(open_price: float, close_price: float):
    return [{"date": "2026-05-04", "open": open_price, "close": close_price}]


def _ohlcv_rows(closes: list[float]):
    dates = ["2026-05-04", "2026-05-05", "2026-05-06"]
    return [
        {"date": date, "open": close_price, "close": close_price}
        for date, close_price in zip(dates, closes)
    ]


def test_language_features_match_negative_packet_threshold():
    features = language_features(_row())

    assert features["language_bucket"] == "negative_language"
    assert features["language_score"] <= -2
    assert features["negative_phrase_hits"] >= 3


def test_build_sec_event_queue_is_default_off_and_freezes_counterfactuals():
    queue = build_sec_event_queue(
        [_row()],
        as_of="2026-05-04",
        ohlcv_by_ticker={"LITE": _ohlcv(100.0, 98.0)},
        spy_ohlcv=_ohlcv(100.0, 101.0),
        core_signals=[{"ticker": "NVDA", "strategy": "trend_long", "confidence_score": 0.91}],
        source_path="data/non_ohlcv/sec_filing_text_sample.jsonl",
    )

    assert queue["queue_name"] == QUEUE_NAME
    assert queue["enabled"] is False
    assert queue["candidate_count"] == 1
    candidate = queue["candidates"][0]
    assert candidate["ticker"] == "LITE"
    assert candidate["trade_enabled"] is False
    assert candidate["reaction_excess_return"] < 0
    assert candidate["counterfactual"]["alternatives"][0]["ticker"] == "NVDA"
    assert candidate["counterfactual"]["alternatives"][-1]["type"] == "cash"
    assert queue["production_impact"]["alters_orders"] is False


def test_governance_queue_is_default_off_and_freezes_counterfactuals():
    row = _row(
        ticker="CRDO",
        accession_number="0002",
        eight_k_item_codes=["5.07"],
        combined_text="Shareholder meeting voting results.",
    )
    queue = build_sec_governance_procedural_queue(
        [row],
        as_of="2026-05-04",
        ohlcv_by_ticker={"CRDO": _ohlcv(100.0, 99.0)},
        spy_ohlcv=_ohlcv(100.0, 100.0),
        core_signals=[{"ticker": "NVDA", "strategy": "breakout_long", "confidence_score": 0.93}],
        source_path="data/non_ohlcv/sec_filing_text_sample.jsonl",
    )

    assert queue["queue_name"] == GOVERNANCE_QUEUE_NAME
    assert queue["enabled"] is False
    assert queue["candidate_count"] == 1
    candidate = queue["candidates"][0]
    assert candidate["ticker"] == "CRDO"
    assert candidate["trade_enabled"] is False
    assert candidate["semantic_subcategory"] == "shareholder_vote"
    assert candidate["reaction_bucket"] == "negative_excess_0_to_minus_2pct"
    assert candidate["target_cell"] == "shareholder_vote|negative_excess_0_to_minus_2pct"
    assert candidate["counterfactual"]["alternatives"][0]["ticker"] == "NVDA"
    assert candidate["counterfactual"]["alternatives"][-1]["type"] == "cash"
    assert queue["production_impact"]["alters_orders"] is False


def test_leadership_queue_is_default_off_and_freezes_counterfactuals():
    row = _row(
        ticker="CEOX",
        accession_number="0003",
        eight_k_item_codes=["5.02", "9.01"],
        combined_text="Departure of directors or certain officers. A new CEO was appointed.",
    )
    queue = build_sec_leadership_change_queue(
        [row],
        as_of="2026-05-04",
        ohlcv_by_ticker={"CEOX": _ohlcv(100.0, 96.0)},
        spy_ohlcv=_ohlcv(100.0, 100.0),
        core_signals=[{"ticker": "NVDA", "strategy": "trend_long", "confidence_score": 0.91}],
        source_path="data/non_ohlcv/sec_filing_text_sample.jsonl",
    )

    assert queue["queue_name"] == LEADERSHIP_QUEUE_NAME
    assert queue["enabled"] is False
    assert queue["candidate_count"] == 1
    candidate = queue["candidates"][0]
    assert candidate["ticker"] == "CEOX"
    assert candidate["trade_enabled"] is False
    assert candidate["semantic_subcategory"] == "leadership_change"
    assert candidate["reaction_bucket"] == "negative_excess_le_minus_2pct"
    assert candidate["target_cell"] == "leadership_change|negative_excess_le_minus_2pct"
    assert candidate["reaction_excess_return"] <= -0.02
    assert candidate["counterfactual"]["alternatives"][0]["ticker"] == "NVDA"
    assert candidate["counterfactual"]["alternatives"][-1]["type"] == "cash"
    assert queue["production_impact"]["alters_orders"] is False


def test_financial_report_t1_queue_is_default_off_and_uses_positive_excess_drift():
    row = _row(
        ticker="FRPT",
        accession_number="0004",
        eight_k_item_codes=["2.02", "9.01"],
        combined_text="Quarterly financial results.",
    )
    queue = build_sec_financial_report_t1_queue(
        [row],
        as_of="2026-05-05",
        ohlcv_by_ticker={"FRPT": _ohlcv_rows([100.0, 103.0, 104.0])},
        spy_ohlcv=_ohlcv_rows([100.0, 101.0, 101.5]),
        core_signals=[{"ticker": "NVDA", "strategy": "trend_long", "confidence_score": 0.91}],
        source_path="data/non_ohlcv/sec_filing_events_sample.jsonl",
    )

    assert queue["queue_name"] == FINANCIAL_REPORT_T1_QUEUE_NAME
    assert queue["enabled"] is False
    assert queue["candidate_count"] == 1
    candidate = queue["candidates"][0]
    assert candidate["ticker"] == "FRPT"
    assert candidate["event_family"] == "earnings_8k"
    assert candidate["cohort"] == "other_equity"
    assert candidate["t1_date"] == "2026-05-05"
    assert candidate["shadow_entry_date"] == "2026-05-06"
    assert candidate["t1_excess_return_vs_spy"] == 0.02
    assert candidate["trade_enabled"] is False
    assert candidate["counterfactual"]["alternatives"][0]["ticker"] == "NVDA"
    assert queue["production_impact"]["alters_orders"] is False


def test_financial_report_t1_queue_rejects_nonfinancial_or_nonexcess_rows():
    good_periodic = _row(
        ticker="PER",
        accession_number="0005",
        form_type="10-Q",
        form_base="10-Q",
        eight_k_item_codes=[],
    )
    governance = _row(
        ticker="GOV",
        accession_number="0006",
        eight_k_item_codes=["5.02"],
    )

    queue = build_sec_financial_report_t1_queue(
        [good_periodic, governance],
        as_of="2026-05-05",
        ohlcv_by_ticker={
            "PER": _ohlcv_rows([100.0, 100.5, 101.0]),
            "GOV": _ohlcv_rows([100.0, 110.0, 111.0]),
        },
        spy_ohlcv=_ohlcv_rows([100.0, 101.0, 102.0]),
    )

    assert queue["candidate_count"] == 0
    event = {
        "status": "ok",
        "event_family": "periodic_report",
        "cohort": "other_equity",
        "price_status": "covered",
        "drift_bucket": "positive_t1_excess_drift",
        "t1_excess_return_vs_spy": 0.01,
    }
    assert qualifies_sec_financial_report_t1_event(event) is True


def test_financial_report_t1_queue_requires_accepted_excess_floor():
    weak = _row(
        ticker="WEAK",
        accession_number="0010",
        eight_k_item_codes=["2.02", "9.01"],
    )
    strong = _row(
        ticker="STRONG",
        accession_number="0011",
        eight_k_item_codes=["2.02", "9.01"],
    )

    queue = build_sec_financial_report_t1_queue(
        [weak, strong],
        as_of="2026-05-05",
        ohlcv_by_ticker={
            "WEAK": _ohlcv_rows([100.0, 102.0, 103.0]),
            "STRONG": _ohlcv_rows([100.0, 103.0, 104.0]),
        },
        spy_ohlcv=_ohlcv_rows([100.0, 101.5, 102.0]),
    )

    assert FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY == 0.01
    assert queue["parameters"]["min_t1_excess_return_vs_spy"] == 0.01
    assert queue["candidate_count"] == 1
    assert queue["candidates"][0]["ticker"] == "STRONG"

    base_event = {
        "status": "ok",
        "event_family": "earnings_8k",
        "cohort": "other_equity",
        "price_status": "covered",
        "drift_bucket": "positive_t1_excess_drift",
    }
    assert qualifies_sec_financial_report_t1_event(
        {
            **base_event,
            "t1_excess_return_vs_spy": (
                FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY - 0.0001
            ),
        }
    ) is False
    assert qualifies_sec_financial_report_t1_event(
        {
            **base_event,
            "t1_excess_return_vs_spy": FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
        }
    ) is True


def test_financial_report_t1_queue_excludes_platform_pool_and_missing_cohort():
    platform = _row(
        ticker="PLAT",
        accession_number="0007",
        cohort="platform_pool",
        eight_k_item_codes=["2.02", "9.01"],
    )
    missing = _row(
        ticker="MISS",
        accession_number="0008",
        eight_k_item_codes=["2.02", "9.01"],
    )
    missing.pop("cohort")
    allowed = _row(
        ticker="KEEP",
        accession_number="0009",
        cohort="other_equity",
        eight_k_item_codes=["2.02", "9.01"],
    )

    queue = build_sec_financial_report_t1_queue(
        [platform, missing, allowed],
        as_of="2026-05-05",
        ohlcv_by_ticker={
            "PLAT": _ohlcv_rows([100.0, 103.0, 104.0]),
            "MISS": _ohlcv_rows([100.0, 103.0, 104.0]),
            "KEEP": _ohlcv_rows([100.0, 103.0, 104.0]),
        },
        spy_ohlcv=_ohlcv_rows([100.0, 101.0, 101.5]),
    )

    assert queue["candidate_count"] == 1
    assert queue["candidates"][0]["ticker"] == "KEEP"
    assert queue["candidates"][0]["cohort"] == "other_equity"

    base_event = {
        "status": "ok",
        "event_family": "earnings_8k",
        "price_status": "covered",
        "drift_bucket": "positive_t1_excess_drift",
        "t1_excess_return_vs_spy": 0.02,
    }
    assert qualifies_sec_financial_report_t1_event({**base_event, "cohort": "platform_pool"}) is False
    assert qualifies_sec_financial_report_t1_event(base_event) is False


def test_governance_semantics_and_reaction_buckets_match_frozen_cells():
    assert governance_semantic_subcategory({"eight_k_item_codes": ["5.07"]}) == "shareholder_vote"
    assert (
        governance_semantic_subcategory({"eight_k_item_codes": ["5.03", "9.01"]})
        == "charter_or_securities_change"
    )
    assert governance_semantic_subcategory({"eight_k_item_codes": ["9.01"]}) == "exhibit_only"
    assert governance_reaction_bucket(0.015) == "positive_excess_0_to_2pct"
    assert governance_reaction_bucket(-0.015) == "negative_excess_0_to_minus_2pct"
    assert leadership_semantic_subcategory({"eight_k_item_codes": ["5.02"]}) == "leadership_change"


def test_earnings_item_2_02_is_not_governance_candidate():
    event = {
        **_row(eight_k_item_codes=["2.02", "9.01"]),
        "price_status": "covered",
        "reaction_excess_return": -0.01,
    }

    assert qualifies_sec_governance_procedural_event(event) is False


def test_item_5_02_needs_negative_two_pct_excess_reaction_for_leadership_queue():
    mild = {
        **_row(eight_k_item_codes=["5.02"]),
        "price_status": "covered",
        "reaction_excess_return": -0.019,
    }
    strong = {**mild, "reaction_excess_return": -0.02}
    wrong_item = {**strong, "eight_k_item_codes": ["5.07"]}

    assert qualifies_sec_leadership_change_event(mild) is False
    assert qualifies_sec_leadership_change_event(strong) is True
    assert qualifies_sec_leadership_change_event(wrong_item) is False


def test_nonnegative_reaction_is_not_queued():
    event = {
        **_row(),
        **language_features(_row()),
        "price_status": "covered",
        "reaction_excess_return": 0.01,
    }

    assert qualifies_sec_negative_reaction_event(event) is False

    queue = build_sec_event_queue(
        [_row()],
        as_of="2026-05-04",
        ohlcv_by_ticker={"LITE": _ohlcv(100.0, 101.0)},
        spy_ohlcv=_ohlcv(100.0, 100.0),
    )

    assert queue["candidate_count"] == 0


def test_build_forward_queue_from_sec_filing_text_handles_missing_source(tmp_path: Path):
    queue = build_forward_queue_from_sec_filing_text(
        data_dir=tmp_path,
        as_of="2026-05-04",
        ohlcv_by_ticker={},
        spy_ohlcv=[],
    )

    assert queue["enabled"] is False
    assert queue["candidate_count"] == 0
    assert queue["data_source"]["status"] == "missing_sec_filing_text_jsonl"


def test_build_forward_queue_from_sec_filing_text_honors_explicit_daily_source(tmp_path: Path):
    stale = tmp_path / "sec_filing_text_20241002_20260421.jsonl"
    stale.write_text(
        '{"status":"ok","ticker":"LITE","usable_trade_date":"2026-05-04"}\n',
        encoding="utf-8",
    )
    daily = tmp_path / "sec_filing_text_20260504.jsonl"

    queue = build_forward_queue_from_sec_filing_text(
        data_dir=tmp_path,
        as_of="2026-05-04",
        ohlcv_by_ticker={},
        spy_ohlcv=[],
        source_path=daily,
    )

    assert queue["enabled"] is False
    assert queue["candidate_count"] == 0
    assert queue["data_source"]["status"] == "missing_sec_filing_text_jsonl"


def test_build_forward_leadership_queue_handles_missing_source(tmp_path: Path):
    queue = build_forward_leadership_queue_from_sec_filing_text(
        data_dir=tmp_path,
        as_of="2026-05-04",
        ohlcv_by_ticker={},
        spy_ohlcv=[],
    )

    assert queue["enabled"] is False
    assert queue["candidate_count"] == 0
    assert queue["data_source"]["status"] == "missing_sec_filing_text_jsonl"


def test_build_forward_financial_report_t1_queue_handles_missing_source(tmp_path: Path):
    queue = build_forward_financial_report_t1_queue_from_sec_filing_events(
        data_dir=tmp_path,
        as_of="2026-05-05",
        ohlcv_by_ticker={},
        spy_ohlcv=[],
    )

    assert queue["enabled"] is False
    assert queue["candidate_count"] == 0
    assert queue["data_source"]["status"] == "missing_sec_filing_events_jsonl"


def test_shared_queue_policy_replays_exp010_primary_packet():
    from experiments.exp_20260504_010_sec_event_sleeve_backtest import TEXT_PATH, build_primary_candidates

    expected, price_map = build_primary_candidates()
    text_rows = load_sec_filing_text_rows(TEXT_PATH)
    replayed = []
    for as_of in sorted({row["usable_trade_date"] for row in expected}):
        queue = build_sec_event_queue(
            text_rows,
            as_of=as_of,
            ohlcv_by_ticker=price_map,
            spy_ohlcv=price_map["SPY"],
        )
        replayed.extend(queue["candidates"])

    expected_keys = {
        (row["ticker"], row["accession_number"], row["usable_trade_date"])
        for row in expected
    }
    replayed_keys = {
        (row["ticker"], row["accession_number"], row["usable_trade_date"])
        for row in replayed
    }
    assert replayed_keys == expected_keys


def test_report_generator_renders_sec_queue_without_enabling_trades():
    from report_generator import generate_daily_report

    queue = build_sec_event_queue(
        [_row()],
        as_of="2026-05-04",
        ohlcv_by_ticker={"LITE": _ohlcv(100.0, 98.0)},
        spy_ohlcv=_ohlcv(100.0, 101.0),
    )
    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        sec_event_queue=queue,
    )

    assert "SEC NEGATIVE-REACTION EVENT QUEUE" in report
    assert "Enabled: False" in report
    assert "LITE" in report
    assert "observe only" in report


def test_report_generator_renders_sec_governance_queue_without_orders():
    from report_generator import generate_daily_report

    queue = build_sec_governance_procedural_queue(
        [_row(ticker="CRDO", eight_k_item_codes=["5.07"])],
        as_of="2026-05-04",
        ohlcv_by_ticker={"CRDO": _ohlcv(100.0, 99.0)},
        spy_ohlcv=_ohlcv(100.0, 100.0),
    )
    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        sec_governance_event_queue=queue,
    )

    assert "SEC GOVERNANCE/PROCEDURAL EVENT QUEUE" in report
    assert "Enabled: False" in report
    assert "CRDO" in report
    assert "paper only" in report


def test_report_generator_renders_sec_leadership_queue_without_orders():
    from report_generator import generate_daily_report

    queue = build_sec_leadership_change_queue(
        [_row(ticker="CEOX", eight_k_item_codes=["5.02"])],
        as_of="2026-05-04",
        ohlcv_by_ticker={"CEOX": _ohlcv(100.0, 96.0)},
        spy_ohlcv=_ohlcv(100.0, 100.0),
    )
    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        sec_leadership_event_queue=queue,
    )

    assert "SEC LEADERSHIP-CHANGE EVENT QUEUE" in report
    assert "Enabled: False" in report
    assert "CEOX" in report
    assert "paper only" in report


def test_report_generator_renders_sec_financial_report_t1_queue_without_orders():
    from report_generator import generate_daily_report

    queue = build_sec_financial_report_t1_queue(
        [_row(ticker="FRPT", accession_number="0004")],
        as_of="2026-05-05",
        ohlcv_by_ticker={"FRPT": _ohlcv_rows([100.0, 103.0, 104.0])},
        spy_ohlcv=_ohlcv_rows([100.0, 101.0, 101.5]),
    )
    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        sec_financial_report_t1_queue=queue,
    )

    assert "SEC FINANCIAL-REPORT T+1 DRIFT QUEUE" in report
    assert "Enabled: False" in report
    assert "FRPT" in report
    assert "paper only" in report
