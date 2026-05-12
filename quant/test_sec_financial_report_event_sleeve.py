from __future__ import annotations

import pytest

from sec_financial_report_event_sleeve import (
    DEFAULT_10Q_PERIODIC_REPORT_NOTIONAL_SCALAR,
    DEFAULT_CONFIG,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
    SLEEVE_NAME,
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
    return candidate


def _state_from_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    state = empty_sec_financial_report_event_sleeve_state()
    state["pending_entries"] = list(snapshot.get("pending_entries") or [])
    state["open_positions"] = list(snapshot.get("open_positions") or [])
    state["closed_positions"] = list(snapshot.get("closed_positions") or [])
    state["skipped_entries"] = list(snapshot.get("skipped_entries") or [])
    return state


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

    second = build_sec_financial_report_event_sleeve_snapshot(
        sec_financial_report_t1_queue=_queue(),
        as_of="2026-05-06",
        open_prices={"FRPT": 100.0},
        current_prices={"FRPT": 101.0},
        state=_state_from_snapshot(first),
        config={"hold_days": 1},
        persist=False,
    )

    assert second["filled_count"] == 1
    assert second["open_position_count"] == 1
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
