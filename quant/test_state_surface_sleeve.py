from __future__ import annotations

from datetime import date, timedelta

from report_generator import generate_daily_report
from state_surface_sleeve import (
    SLEEVE_NAME,
    build_state_surface_queue,
    build_state_surface_sleeve_snapshot,
    empty_state_surface_sleeve_state,
)


def _rows(start_price: float, daily_step: float, volume: int = 1_000):
    start = date(2025, 9, 17)
    rows = []
    price = start_price
    for idx in range(230):
        price = price * (1.0 + daily_step)
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": round(price * 0.995, 4),
                "high": round(price * 1.01, 4),
                "low": round(price * 0.99, 4),
                "close": round(price, 4),
                "volume": volume + idx,
            }
        )
    return rows


def _ohlcv():
    return {
        "SPY": _rows(100.0, 0.0005),
        "QQQ": _rows(100.0, 0.0006),
        "IWM": _rows(100.0, 0.0002),
        "AAA": _rows(50.0, 0.0020),
        "BBB": _rows(50.0, 0.0016),
        "CCC": _rows(50.0, 0.0012),
    }


def _ohlcv_negative_benchmarks():
    return {
        "SPY": _rows(100.0, -0.0005),
        "QQQ": _rows(100.0, -0.0006),
        "IWM": _rows(100.0, -0.0004),
        "AAA": _rows(50.0, 0.0020),
        "BBB": _rows(50.0, 0.0016),
        "CCC": _rows(50.0, 0.0012),
    }


def test_state_surface_queue_is_default_off_and_excludes_core_candidates():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv(),
        universe=["AAA", "BBB", "CCC"],
        core_signals=[{"ticker": "AAA", "strategy": "trend_long", "confidence_score": 0.91}],
    )

    assert queue["queue_name"] == "STATE_SURFACE_SATELLITE_QUEUE"
    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["scored_candidate_count"] == 3
    assert {row["ticker"] for row in queue["scored_candidates"]} == {"AAA", "BBB", "CCC"}
    assert queue["benchmark_momentum_gate"]["allowed"] is True
    assert queue["candidate_count"] == 2
    assert {row["ticker"] for row in queue["candidates"]} == {"BBB", "CCC"}
    assert all(row["benchmark_momentum_gate"]["allowed"] is True for row in queue["candidates"])
    assert queue["candidates"][0]["counterfactuals"]["alternatives"][-1]["type"] == "cash"
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_benchmark_momentum_gate_blocks_paper_candidates_without_orders():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_negative_benchmarks(),
        universe=["AAA", "BBB", "CCC"],
        config={"max_candidates": 2},
    )

    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["scored_candidate_count"] == 3
    assert queue["candidate_count"] == 0
    assert queue["blocked_candidate_count"] == 2
    assert queue["benchmark_momentum_gate"]["allowed"] is False
    assert queue["benchmark_momentum_gate"]["reasons"] == ["benchmark_momentum_nonpositive"]
    assert queue["benchmark_momentum_gate"]["trade_enabled_after_gate"] is False
    assert queue["production_impact"]["alters_orders"] is False

    snapshot = build_state_surface_sleeve_snapshot(
        state_surface_queue=queue,
        as_of="2026-05-04",
        state=empty_state_surface_sleeve_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["blocked_candidate_count"] == 2
    assert snapshot["benchmark_momentum_gate"]["allowed"] is False
    assert snapshot["production_impact"]["alters_orders"] is False


def test_state_surface_sleeve_tracks_paper_entries_without_orders():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv(),
        universe=["AAA", "BBB", "CCC"],
        config={"max_candidates": 1},
    )
    state = empty_state_surface_sleeve_state()
    first = build_state_surface_sleeve_snapshot(
        state_surface_queue=queue,
        as_of="2026-05-04",
        state=state,
        persist=False,
    )
    next_state = empty_state_surface_sleeve_state()
    next_state["pending_entries"] = first["pending_entries"]
    ticker = first["pending_entries"][0]["ticker"]

    second = build_state_surface_sleeve_snapshot(
        state_surface_queue={"candidates": [], "candidate_count": 0},
        as_of="2026-05-05",
        state=next_state,
        open_prices={ticker: 100.0},
        current_prices={ticker: 101.0},
        persist=False,
    )

    assert second["sleeve"] == SLEEVE_NAME
    assert second["enabled"] is False
    assert second["trade_enabled"] is False
    assert second["filled_count"] == 1
    assert second["open_position_count"] == 1
    assert second["production_impact"]["alters_orders"] is False


def test_report_generator_renders_state_surface_without_orders():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv(),
        universe=["AAA", "BBB", "CCC"],
        config={"max_candidates": 1},
    )
    snapshot = build_state_surface_sleeve_snapshot(
        state_surface_queue=queue,
        as_of="2026-05-04",
        state=empty_state_surface_sleeve_state(),
        persist=False,
    )

    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        state_surface_sleeve=snapshot,
    )

    assert "STATE-SURFACE SATELLITE PAPER SLEEVE" in report
    assert "Trade enabled: False" in report
    assert "paper only" in report
