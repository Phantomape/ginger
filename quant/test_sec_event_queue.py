from __future__ import annotations

from pathlib import Path

from sec_event_queue import (
    GOVERNANCE_QUEUE_NAME,
    QUEUE_NAME,
    build_sec_governance_procedural_queue,
    build_forward_queue_from_sec_filing_text,
    build_sec_event_queue,
    governance_reaction_bucket,
    governance_semantic_subcategory,
    language_features,
    load_sec_filing_text_rows,
    qualifies_sec_governance_procedural_event,
    qualifies_sec_negative_reaction_event,
)


def _row(**overrides):
    row = {
        "status": "ok",
        "ticker": "LITE",
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


def test_governance_semantics_and_reaction_buckets_match_frozen_cells():
    assert governance_semantic_subcategory({"eight_k_item_codes": ["5.07"]}) == "shareholder_vote"
    assert (
        governance_semantic_subcategory({"eight_k_item_codes": ["5.03", "9.01"]})
        == "charter_or_securities_change"
    )
    assert governance_semantic_subcategory({"eight_k_item_codes": ["9.01"]}) == "exhibit_only"
    assert governance_reaction_bucket(0.015) == "positive_excess_0_to_2pct"
    assert governance_reaction_bucket(-0.015) == "negative_excess_0_to_minus_2pct"


def test_earnings_item_2_02_is_not_governance_candidate():
    event = {
        **_row(eight_k_item_codes=["2.02", "9.01"]),
        "price_status": "covered",
        "reaction_excess_return": -0.01,
    }

    assert qualifies_sec_governance_procedural_event(event) is False


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
