from __future__ import annotations

import pytest

from sec_financial_report_event_sleeve import (
    DEFAULT_10Q_PERIODIC_REPORT_NOTIONAL_SCALAR,
    DEFAULT_CONFIG,
    DEFAULT_EARNINGS_RELEASE_TEXT_SPY_T1_CONTEXT_SCALAR,
    DEFAULT_EARNINGS_RELEASE_TEXT_SPY_T1_RETURN_MIN,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS,
    DEFAULT_NEUTRAL_UNDERREACTION_NOTIONAL_SCALAR,
    DEFAULT_NEUTRAL_UNDERREACTION_SPY_T1_CONTEXT_SCALAR,
    DEFAULT_NEUTRAL_UNDERREACTION_SPY_T1_RETURN_MIN,
    DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
    DEFAULT_RS20_LEADER_MIN_EXCESS_RETURN,
    DEFAULT_RS20_LEADER_NOTIONAL_SCALAR,
    SLEEVE_NAME,
    build_fact_tone_gap_attribution,
    build_sec_financial_report_event_sleeve_snapshot,
    empty_sec_financial_report_event_sleeve_state,
)


def _queue(*candidates: dict[str, object]) -> dict[str, object]:
    return {
        "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_FORWARD_QUEUE",
        "enabled": False,
        "candidate_count": len(candidates),
        "data_source": {"status": "loaded"},
        "candidates": list(candidates),
    }


def _candidate(
    ticker: str = "FRPT",
    accession: str = "0001",
    t1_excess: float = 0.03,
    date: str = "2026-05-04",
    event_family: str = "earnings_8k",
    form_base: str | None = None,
    language_bucket: str | None = None,
    spy_t1_return: float | None = None,
    text_event_type: str | None = None,
    positive_phrase_hits: list[str] | None = None,
    negative_phrase_hits: list[str] | None = None,
    guidance_raise_hits: list[str] | None = None,
    guidance_cut_hits: list[str] | None = None,
    ticker_minus_spy_ret20: float | None = None,
) -> dict[str, object]:
    candidate = {
        "ticker": ticker,
        "usable_trade_date": date,
        "accession_number": accession,
        "event_family": event_family,
        "t1_date": "2026-05-05",
        "t1_excess_return_vs_spy": t1_excess,
        "trade_enabled": False,
    }
    if form_base:
        candidate["form_base"] = form_base
    if language_bucket:
        candidate["language_bucket"] = language_bucket
    if spy_t1_return is not None:
        candidate["spy_t1_return"] = spy_t1_return
    if text_event_type is not None:
        candidate["text_event_type"] = text_event_type
    if positive_phrase_hits is not None:
        candidate["positive_phrase_hits"] = positive_phrase_hits
    if negative_phrase_hits is not None:
        candidate["negative_phrase_hits"] = negative_phrase_hits
    if guidance_raise_hits is not None:
        candidate["guidance_raise_hits"] = guidance_raise_hits
    if guidance_cut_hits is not None:
        candidate["guidance_cut_hits"] = guidance_cut_hits
    if ticker_minus_spy_ret20 is not None:
        candidate["ticker_minus_spy_ret20"] = ticker_minus_spy_ret20
        candidate["rs20_leader_bucket"] = (
            "leader_ge_5pp"
            if ticker_minus_spy_ret20 >= DEFAULT_RS20_LEADER_MIN_EXCESS_RETURN
            else "below_5pp_or_missing"
        )
    return candidate


def _state_from_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    state = empty_sec_financial_report_event_sleeve_state()
    state["pending_entries"] = list(snapshot.get("pending_entries") or [])
    state["open_positions"] = list(snapshot.get("open_positions") or [])
    state["closed_positions"] = list(snapshot.get("closed_positions") or [])
    state["skipped_entries"] = list(snapshot.get("skipped_entries") or [])
    return state


def test_fact_tone_gap_attribution_is_read_only_with_provenance():
    attribution = build_fact_tone_gap_attribution(
        _candidate(
            "ERN",
            language_bucket="positive_language",
            text_event_type="earnings_release_text",
            positive_phrase_hits=["revenue increased"],
            guidance_raise_hits=["raised outlook"],
        )
    )

    assert attribution["rule_version"] == "sec_fact_tone_gap_bucket_v1"
    assert attribution["fact_tone_gap_bucket"] == "fact_improvement_positive_tone"
    assert attribution["default_off_attribution_only"] is True
    assert attribution["provenance"]["ticker"] == "ERN"
    assert attribution["evidence_counts"]["positive_phrase_hits"] == 1
    assert attribution["evidence_span"][0]["source"] == "sec_financial_report_t1_queue"
    assert attribution["alters_orders"] is False


def test_financial_report_sleeve_freezes_pending_then_paper_fills_and_closes():
    first = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(_candidate()),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        config={"hold_days": 1},
        persist=False,
    )

    assert first["sleeve"] == SLEEVE_NAME
    assert first["enabled"] is False
    assert first["trade_enabled"] is False
    assert first["new_pending_count"] == 1
    assert first["pending_count"] == 1
    assert first["open_position_count"] == 0
    assert first["production_impact"]["alters_orders"] is False
    assert first["pending_entries"][0]["paper_notional_usd"] == 15_000.0
    assert first["pending_entries"][0]["paper_notional_frozen"] is True

    second = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"FRPT": 100.0},
        current_prices={"FRPT": 101.0},
        state=_state_from_snapshot(first),
        config={"hold_days": 1, "event_notional_usd": 2_500.0},
        persist=False,
    )

    assert second["filled_count"] == 1
    assert second["open_position_count"] == 1
    assert second["open_positions"][0]["notional"] == 15_000.0
    assert second["open_positions"][0]["trade_enabled"] is False

    third = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-07",
        current_prices={"FRPT": 110.0},
        state=_state_from_snapshot(second),
        config={"hold_days": 1},
        persist=False,
    )

    assert third["closed_count_today"] == 1
    assert third["open_position_count"] == 0
    assert third["realized_pnl_to_date"] == pytest.approx(1447.5)
    assert third["closed_positions_today"][0]["trade_enabled"] is False


def test_financial_report_sleeve_ignores_stale_price_dates():
    first = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(_candidate()),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        config={"hold_days": 1},
        persist=False,
    )
    state = _state_from_snapshot(first)
    state["open_positions"] = [
        {
            "decision_id": "open-frpt",
            "ticker": "FRPT",
            "entry_date": "2026-05-05",
            "entry_price": 100.0,
            "notional": 15_000.0,
            "observed_trading_days": 0,
            "last_seen_date": "2026-05-05",
            "trade_enabled": False,
        }
    ]

    snapshot = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"FRPT": 100.0},
        current_prices={"FRPT": 110.0},
        open_price_dates={"FRPT": "2026-05-05"},
        current_price_dates={"FRPT": "2026-05-05"},
        state=state,
        config={"hold_days": 1, "max_positions": 2},
        persist=False,
    )

    assert snapshot["filled_count"] == 0
    assert snapshot["closed_count_today"] == 0
    assert snapshot["pending_count"] == 1
    assert snapshot["open_position_count"] == 1
    assert snapshot["open_positions"][0]["observed_trading_days"] == 0


def test_financial_report_sleeve_exposes_fact_tone_gap_bucket_on_paper_candidates():
    first = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(
            _candidate(
                "ERN",
                "0001",
                0.04,
                language_bucket="positive_language",
                text_event_type="earnings_release_text",
                positive_phrase_hits=["net sales improved"],
            )
        ),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        persist=False,
    )
    attribution = first["candidates"][0]["fact_tone_gap_attribution"]

    assert attribution["fact_tone_gap_bucket"] == "fact_improvement_positive_tone"
    assert first["pending_entries"][0]["candidate"]["fact_tone_gap_attribution"] == attribution

    second = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"ERN": 100.0},
        current_prices={"ERN": 101.0},
        state=_state_from_snapshot(first),
        persist=False,
    )

    assert second["open_positions"][0]["fact_tone_gap_bucket"] == (
        "fact_improvement_positive_tone"
    )
    assert second["open_positions"][0]["fact_tone_gap_attribution"]["read_only"] is True


def test_financial_report_sleeve_prioritizes_strongest_t1_excess():
    first = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(
            _candidate("LOW", "0001", 0.01),
            _candidate("HIGH", "0002", 0.05),
        ),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        persist=False,
    )
    second = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"LOW": 20.0, "HIGH": 30.0},
        current_prices={"LOW": 20.0, "HIGH": 30.0},
        state=_state_from_snapshot(first),
        config={"max_positions": 1},
        persist=False,
    )

    assert second["filled_count"] == 1
    assert second["open_positions"][0]["ticker"] == "HIGH"
    assert second["skipped_count_today"] == 1
    assert second["skipped_entries_today"][0]["ticker"] == "LOW"


def test_financial_report_sleeve_default_capacity_tracks_three_paper_positions_without_orders():
    first = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(
            _candidate("LOW", "0001", 0.01),
            _candidate("MID", "0002", 0.02),
            _candidate("HIGH", "0003", 0.05),
            _candidate("TOP", "0004", 0.08),
        ),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        persist=False,
    )
    second = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"LOW": 10.0, "MID": 20.0, "HIGH": 30.0, "TOP": 40.0},
        current_prices={"LOW": 10.0, "MID": 20.0, "HIGH": 30.0, "TOP": 40.0},
        state=_state_from_snapshot(first),
        persist=False,
    )

    assert DEFAULT_MAX_POSITIONS == 3
    assert DEFAULT_CONFIG["max_positions"] == 3
    assert DEFAULT_CONFIG["event_notional_usd"] == 15_000.0
    assert second["parameters"]["max_positions"] == 3
    assert second["parameters"]["event_notional_usd"] == 15_000.0
    assert second["filled_count"] == 3
    assert second["open_position_count"] == 3
    assert second["skipped_count_today"] == 1
    assert {position["ticker"] for position in second["open_positions"]} == {
        "TOP",
        "HIGH",
        "MID",
    }
    assert second["skipped_entries_today"][0]["ticker"] == "LOW"
    assert second["trade_enabled"] is False
    assert all(position["trade_enabled"] is False for position in second["open_positions"])
    assert all(position["notional"] == 15_000.0 for position in second["open_positions"])


def test_financial_report_sleeve_scales_periodic_report_notional_without_orders():
    first = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(
            _candidate("ERN", "0001", 0.05, event_family="earnings_8k"),
            _candidate(
                "PRD",
                "0002",
                0.04,
                event_family="periodic_report",
                form_base="10-K",
            ),
            _candidate(
                "TENQ",
                "0003",
                0.03,
                event_family="periodic_report",
                form_base="10-Q",
            ),
        ),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        persist=False,
    )
    second = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"ERN": 100.0, "PRD": 100.0, "TENQ": 100.0},
        current_prices={"ERN": 100.0, "PRD": 100.0, "TENQ": 100.0},
        state=_state_from_snapshot(first),
        persist=False,
    )

    by_ticker = {position["ticker"]: position for position in second["open_positions"]}

    assert DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR == 1.25
    assert DEFAULT_10Q_PERIODIC_REPORT_NOTIONAL_SCALAR == 2.0
    assert second["parameters"]["periodic_report_notional_scalar"] == 1.25
    assert second["parameters"]["tenq_periodic_report_notional_scalar"] == 2.0
    assert by_ticker["ERN"]["notional"] == 15_000.0
    assert by_ticker["ERN"]["event_notional_rule"] == "base"
    assert by_ticker["PRD"]["notional"] == 18_750.0
    assert by_ticker["PRD"]["event_notional_scalar"] == 1.25
    assert by_ticker["PRD"]["event_notional_rule"] == "periodic_report_scalar"
    assert by_ticker["TENQ"]["notional"] == 30_000.0
    assert by_ticker["TENQ"]["event_notional_scalar"] == 2.0
    assert by_ticker["TENQ"]["event_notional_rule"] == "periodic_report_10q_scalar"
    assert second["trade_enabled"] is False
    assert all(position["trade_enabled"] is False for position in second["open_positions"])


def test_financial_report_sleeve_scales_neutral_underreaction_without_orders():
    first = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(
            _candidate(
                "NTRL",
                "0001",
                0.02,
                language_bucket="neutral_or_mixed_language",
            ),
            _candidate(
                "HOT",
                "0002",
                0.03,
                language_bucket="neutral_or_mixed_language",
            ),
            _candidate(
                "POS",
                "0003",
                0.02,
                language_bucket="positive_language",
            ),
        ),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        persist=False,
    )
    second = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"NTRL": 100.0, "HOT": 100.0, "POS": 100.0},
        current_prices={"NTRL": 100.0, "HOT": 100.0, "POS": 100.0},
        state=_state_from_snapshot(first),
        persist=False,
    )

    by_ticker = {position["ticker"]: position for position in second["open_positions"]}

    assert DEFAULT_NEUTRAL_UNDERREACTION_NOTIONAL_SCALAR == 2.0
    assert DEFAULT_NEUTRAL_UNDERREACTION_MAX_T1_EXCESS == 0.02
    assert second["parameters"]["neutral_underreaction_notional_enabled"] is True
    assert by_ticker["NTRL"]["notional"] == 30_000.0
    assert by_ticker["NTRL"]["event_notional_scalar"] == 2.0
    assert by_ticker["NTRL"]["event_notional_rule"] == "base+neutral_underreaction_scalar"
    assert by_ticker["HOT"]["notional"] == 15_000.0
    assert by_ticker["HOT"]["event_notional_rule"] == "base"
    assert by_ticker["POS"]["notional"] == 15_000.0
    assert by_ticker["POS"]["event_notional_rule"] == "base"
    assert second["trade_enabled"] is False
    assert all(position["trade_enabled"] is False for position in second["open_positions"])


def test_financial_report_sleeve_scales_neutral_underreaction_market_context_without_orders():
    first = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(
            _candidate(
                "CONF",
                "0001",
                0.018,
                language_bucket="neutral_or_mixed_language",
                spy_t1_return=-0.004,
            ),
            _candidate(
                "ADVR",
                "0002",
                0.018,
                language_bucket="neutral_or_mixed_language",
                spy_t1_return=-0.006,
            ),
            _candidate(
                "MISS",
                "0003",
                0.018,
                language_bucket="neutral_or_mixed_language",
            ),
        ),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        persist=False,
    )
    second = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"CONF": 100.0, "ADVR": 100.0, "MISS": 100.0},
        current_prices={"CONF": 100.0, "ADVR": 100.0, "MISS": 100.0},
        state=_state_from_snapshot(first),
        persist=False,
    )

    by_ticker = {position["ticker"]: position for position in second["open_positions"]}

    assert DEFAULT_NEUTRAL_UNDERREACTION_SPY_T1_CONTEXT_SCALAR == 1.5
    assert DEFAULT_NEUTRAL_UNDERREACTION_SPY_T1_RETURN_MIN == -0.005
    assert second["parameters"]["neutral_underreaction_spy_t1_context_enabled"] is True
    assert by_ticker["CONF"]["notional"] == 45_000.0
    assert by_ticker["CONF"]["event_notional_scalar"] == 3.0
    assert by_ticker["CONF"]["event_notional_rule"] == (
        "base+neutral_underreaction_scalar"
        "+neutral_underreaction_spy_t1_context_scalar"
    )
    assert by_ticker["ADVR"]["notional"] == 30_000.0
    assert by_ticker["ADVR"]["event_notional_rule"] == "base+neutral_underreaction_scalar"
    assert by_ticker["MISS"]["notional"] == 30_000.0
    assert by_ticker["MISS"]["event_notional_rule"] == "base+neutral_underreaction_scalar"
    assert second["trade_enabled"] is False
    assert all(position["trade_enabled"] is False for position in second["open_positions"])


def test_financial_report_sleeve_scales_earnings_release_text_market_context_without_orders():
    first = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(
            _candidate(
                "ERN",
                "0001",
                0.04,
                spy_t1_return=-0.004,
                text_event_type="earnings_release_text",
            ),
            _candidate(
                "ADVR",
                "0002",
                0.03,
                spy_t1_return=-0.006,
                text_event_type="earnings_release_text",
            ),
            _candidate(
                "MISS",
                "0003",
                0.02,
                spy_t1_return=-0.004,
            ),
        ),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        persist=False,
    )
    second = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"ERN": 100.0, "ADVR": 100.0, "MISS": 100.0},
        current_prices={"ERN": 100.0, "ADVR": 100.0, "MISS": 100.0},
        state=_state_from_snapshot(first),
        persist=False,
    )

    by_ticker = {position["ticker"]: position for position in second["open_positions"]}

    assert DEFAULT_EARNINGS_RELEASE_TEXT_SPY_T1_CONTEXT_SCALAR == 1.10
    assert DEFAULT_EARNINGS_RELEASE_TEXT_SPY_T1_RETURN_MIN == -0.005
    assert second["parameters"]["earnings_release_text_spy_t1_context_enabled"] is True
    assert by_ticker["ERN"]["notional"] == pytest.approx(16_500.0)
    assert by_ticker["ERN"]["event_notional_scalar"] == pytest.approx(1.10)
    assert by_ticker["ERN"]["event_notional_rule"] == (
        "base+earnings_release_text_spy_t1_context_scalar"
    )
    assert by_ticker["ADVR"]["notional"] == 15_000.0
    assert by_ticker["ADVR"]["event_notional_rule"] == "base"
    assert by_ticker["MISS"]["notional"] == 15_000.0
    assert by_ticker["MISS"]["event_notional_rule"] == "base"
    assert second["trade_enabled"] is False
    assert all(position["trade_enabled"] is False for position in second["open_positions"])


def test_financial_report_sleeve_scales_rs20_leader_without_orders():
    first = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(
            _candidate("LEAD", "0001", 0.04, ticker_minus_spy_ret20=0.06),
            _candidate("BASE", "0002", 0.03, ticker_minus_spy_ret20=0.04),
        ),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        persist=False,
    )
    second = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"LEAD": 100.0, "BASE": 100.0},
        current_prices={"LEAD": 100.0, "BASE": 100.0},
        state=_state_from_snapshot(first),
        persist=False,
    )

    by_ticker = {position["ticker"]: position for position in second["open_positions"]}

    assert DEFAULT_RS20_LEADER_MIN_EXCESS_RETURN == 0.05
    assert DEFAULT_RS20_LEADER_NOTIONAL_SCALAR == 1.15
    assert second["parameters"]["rs20_leader_notional_enabled"] is True
    assert by_ticker["LEAD"]["notional"] == pytest.approx(17_250.0)
    assert by_ticker["LEAD"]["event_notional_scalar"] == pytest.approx(1.15)
    assert by_ticker["LEAD"]["event_notional_rule"] == (
        "base+rs20_leader_notional_scalar"
    )
    assert by_ticker["BASE"]["notional"] == 15_000.0
    assert by_ticker["BASE"]["event_notional_rule"] == "base"
    assert second["trade_enabled"] is False
    assert all(position["trade_enabled"] is False for position in second["open_positions"])
    assert second["production_impact"]["alters_orders"] is False


def test_financial_report_sleeve_can_disable_rs20_leader_scalar():
    first = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(
            _candidate("LEAD", "0001", 0.04, ticker_minus_spy_ret20=0.06),
        ),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        config={"rs20_leader_notional_enabled": False},
        persist=False,
    )
    second = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"LEAD": 100.0},
        current_prices={"LEAD": 100.0},
        state=_state_from_snapshot(first),
        config={"rs20_leader_notional_enabled": False},
        persist=False,
    )

    assert second["open_positions"][0]["notional"] == 15_000.0
    assert second["open_positions"][0]["event_notional_rule"] == "base"
    assert second["production_impact"]["alters_orders"] is False


def test_financial_report_sleeve_can_disable_neutral_underreaction_scalar():
    first = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(
            _candidate(
                "NTRL",
                "0001",
                0.02,
                language_bucket="neutral_or_mixed_language",
            ),
        ),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        config={"neutral_underreaction_notional_enabled": False},
        persist=False,
    )
    second = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"NTRL": 100.0},
        current_prices={"NTRL": 100.0},
        state=_state_from_snapshot(first),
        config={"neutral_underreaction_notional_enabled": False},
        persist=False,
    )

    assert second["open_positions"][0]["notional"] == 15_000.0
    assert second["open_positions"][0]["event_notional_rule"] == "base"
    assert second["production_impact"]["alters_orders"] is False


def test_report_generator_renders_financial_report_sleeve_without_orders():
    from report_generator import generate_daily_report

    snapshot = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(_candidate()),
        as_of="2026-05-05",
        state=empty_sec_financial_report_event_sleeve_state(),
        persist=False,
    )
    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        sec_financial_report_event_sleeve=snapshot,
    )

    assert "SEC FINANCIAL-REPORT PAPER EVENT SLEEVE" in report
    assert "Trade enabled: False" in report
    assert "Pending: 1" in report
