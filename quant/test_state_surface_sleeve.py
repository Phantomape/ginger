from __future__ import annotations

from datetime import date, timedelta

from report_generator import generate_daily_report
from state_surface_sleeve import (
    SLEEVE_NAME,
    build_state_surface_forward_tail_diagnostics,
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


def _ohlcv_broad_rotation():
    return {
        "SPY": _rows(100.0, 0.0002),
        "QQQ": _rows(100.0, 0.0003),
        "IWM": _rows(100.0, 0.0020),
        "AAA": _rows(50.0, 0.0020),
        "BBB": _rows(50.0, 0.0016),
        "CCC": _rows(50.0, 0.0012),
    }


def _ohlcv_broad_rotation_many():
    return {
        "SPY": _rows(100.0, 0.0002),
        "QQQ": _rows(100.0, 0.0003),
        "IWM": _rows(100.0, 0.0020),
        "AAA": _rows(50.0, 0.0024),
        "BBB": _rows(50.0, 0.0022),
        "CCC": _rows(50.0, 0.0020),
        "DDD": _rows(50.0, 0.0018),
        "EEE": _rows(50.0, 0.0016),
        "FFF": _rows(50.0, 0.0014),
    }


def _ohlcv_flat_benchmarks_broad_rotation():
    return {
        "SPY": _rows(100.0, 0.0),
        "QQQ": _rows(100.0, 0.0),
        "IWM": _rows(100.0, 0.0020),
        "AAA": _rows(50.0, 0.0020),
        "BBB": _rows(50.0, 0.0016),
        "CCC": _rows(50.0, 0.0012),
    }


def test_state_surface_queue_is_default_off_and_excludes_core_candidates():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation(),
        universe=["AAA", "BBB", "CCC"],
        core_signals=[{"ticker": "AAA", "strategy": "trend_long", "confidence_score": 0.91}],
    )

    assert queue["queue_name"] == "STATE_SURFACE_SATELLITE_QUEUE"
    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["scored_candidate_count"] == 3
    assert {row["ticker"] for row in queue["scored_candidates"]} == {"AAA", "BBB", "CCC"}
    assert queue["benchmark_momentum_gate"]["allowed"] is True
    assert queue["surface_eligibility"]["allowed_surfaces"] == ["rotation_breakout_leadership"]
    assert queue["candidate_count"] == 2
    assert {row["ticker"] for row in queue["candidates"]} == {"BBB", "CCC"}
    assert {row["surface"] for row in queue["candidates"]} == {"rotation_breakout_leadership"}
    assert all(row["benchmark_momentum_gate"]["allowed"] is True for row in queue["candidates"])
    assert queue["candidates"][0]["counterfactuals"]["alternatives"][-1]["type"] == "cash"
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_queue_default_admits_top_five_rotation_candidates_only():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation_many(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
    )

    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["parameters"]["max_candidates"] == 5
    assert queue["scored_candidate_count"] == 6
    assert queue["candidate_count"] == 5
    assert [row["queue_rank"] for row in queue["candidates"]] == [1, 2, 3, 4, 5]
    assert queue["market_regime"]["regime"] == "chop"
    assert [row["rank_notional_multiplier"] for row in queue["candidates"]] == [
        1.6625,
        1.315,
        1.0,
        0.675,
        0.35,
    ]
    assert [row["event_notional_usd"] for row in queue["candidates"]] == [
        16625.0,
        13150.0,
        10000.0,
        6750.0,
        3500.0,
    ]
    assert {
        row["rank_notional_profile_name"] for row in queue["candidates"]
    } == {"candidate_breadth_ge4_override"}
    assert {row["candidate_breadth"] for row in queue["candidates"]} == {5}
    assert queue["rank_notional_profile"]["rank_event_notional_usd"] == [
        15000.0,
        12500.0,
        10000.0,
        7500.0,
        5000.0,
    ]
    assert queue["rank_notional_profile"]["regime_rank_event_notional_usd"]["chop"] == [
        16250.0,
        13000.0,
        10000.0,
        7000.0,
        3750.0,
    ]
    assert queue["rank_notional_profile"]["candidate_breadth_min"] == 4
    assert queue["rank_notional_profile"]["candidate_breadth_rank_event_notional_usd"] == [
        16625.0,
        13150.0,
        10000.0,
        6750.0,
        3500.0,
    ]
    assert {row["surface"] for row in queue["candidates"]} == {"rotation_breakout_leadership"}
    assert all(row["ret20_excess_spy_gate"]["allowed"] is True for row in queue["candidates"])
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_queue_can_disable_regime_rank_notional_profile():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation_many(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={
            "rank_notional_regime_profiles_enabled": False,
            "rank_notional_candidate_breadth_profiles_enabled": False,
        },
    )

    assert queue["market_regime"]["regime"] == "chop"
    assert [row["rank_notional_multiplier"] for row in queue["candidates"]] == [
        1.5,
        1.25,
        1.0,
        0.75,
        0.5,
    ]
    assert {
        row["rank_notional_profile_name"] for row in queue["candidates"]
    } == {"default"}
    assert queue["rank_notional_profile"]["regime_profiles_enabled"] is False
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_queue_can_disable_candidate_breadth_rank_notional_profile():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation_many(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={"rank_notional_candidate_breadth_profiles_enabled": False},
    )

    assert queue["market_regime"]["regime"] == "chop"
    assert [row["rank_notional_multiplier"] for row in queue["candidates"]] == [
        1.625,
        1.3,
        1.0,
        0.7,
        0.375,
    ]
    assert {
        row["rank_notional_profile_name"] for row in queue["candidates"]
    } == {"chop_override"}
    assert queue["rank_notional_profile"]["candidate_breadth_profiles_enabled"] is False
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_queue_applies_score_compression_rank_notional_profile():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation_many(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={"rank_notional_score_compression_max_top3_spread": 2.0},
    )

    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["candidate_count"] == 5
    assert [row["rank_notional_multiplier"] for row in queue["candidates"]] == [
        1.35,
        1.45,
        1.05,
        0.675,
        0.35,
    ]
    assert [row["event_notional_usd"] for row in queue["candidates"]] == [
        13500.0,
        14500.0,
        10500.0,
        6750.0,
        3500.0,
    ]
    assert {
        row["rank_notional_profile_name"] for row in queue["candidates"]
    } == {"score_compression_top3_le_2"}
    assert {row["score_top3_spread"] for row in queue["candidates"]} == {0.931526}
    assert queue["rank_notional_profile"]["score_compression_profiles_enabled"] is True
    assert queue["rank_notional_profile"]["score_compression_max_top3_spread"] == 2.0
    assert queue["rank_notional_profile"]["score_compression_rank_event_notional_usd"] == [
        13500.0,
        14500.0,
        10500.0,
        6750.0,
        3500.0,
    ]
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_queue_defaults_to_rotation_surface_candidates_only():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv(),
        universe=["AAA", "BBB", "CCC"],
    )

    assert queue["scored_candidate_count"] == 3
    assert queue["candidate_count"] == 0
    assert queue["surface_blocked_candidate_count"] == 3
    assert {
        row["reason"] for row in queue["surface_blocked_candidates"]
    } == {"surface_not_allowed"}
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_benchmark_momentum_gate_blocks_paper_candidates_without_orders():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_flat_benchmarks_broad_rotation(),
        universe=["AAA", "BBB", "CCC"],
        config={"max_candidates": 2},
    )

    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["scored_candidate_count"] == 3
    assert queue["candidate_count"] == 0
    assert queue["blocked_candidate_count"] == 2
    assert queue["surface_blocked_candidate_count"] == 0
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
    assert snapshot["surface_blocked_candidate_count"] == 0
    assert snapshot["benchmark_momentum_gate"]["allowed"] is False
    assert snapshot["production_impact"]["alters_orders"] is False


def test_state_surface_ret20_excess_spy_gate_blocks_weak_relative_candidates():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation(),
        universe=["AAA", "BBB", "CCC"],
        config={"max_candidates": 3, "ret20_excess_spy_min": 0.03},
    )

    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["ret20_excess_spy_gate"]["enabled"] is True
    assert queue["ret20_excess_spy_gate"]["threshold"] == 0.03
    assert queue["candidate_count"] == 1
    assert queue["candidates"][0]["ticker"] == "AAA"
    assert all(
        row["ret20_excess_spy_gate"]["allowed"] is True
        for row in queue["candidates"]
    )
    assert queue["blocked_candidate_count"] == 2
    assert {
        row["reason"] for row in queue["blocked_candidates"]
    } == {"ret20_excess_spy_gate_blocked"}
    assert all(
        "ret20_excess_spy_below_floor" in row["ret20_excess_spy_gate"]["reasons"]
        for row in queue["blocked_candidates"]
    )
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_sleeve_tracks_paper_entries_without_orders():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation(),
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
    assert first["pending_entries"][0]["event_notional_usd"] == 16250.0
    assert first["pending_entries"][0]["rank_notional_profile_name"] == "chop_override"
    assert first["pending_entries"][0]["market_regime"]["regime"] == "chop"
    assert first["rank_notional_profile"]["rank_event_notional_usd"][0] == 15000.0
    assert first["rank_notional_profile"]["regime_rank_event_notional_usd"]["chop"][0] == 16250.0
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
    assert second["open_positions"][0]["notional"] == 16250.0
    assert second["open_positions"][0]["rank_notional_multiplier"] == 1.625
    assert second["open_positions"][0]["rank_notional_profile_name"] == "chop_override"
    assert second["open_positions"][0]["market_regime"]["regime"] == "chop"
    assert second["tail_diagnostics"]["read_only"] is True
    assert second["production_impact"]["alters_orders"] is False


def test_state_surface_forward_tail_gate_blocks_top5_concentration_without_orders():
    concentrated = [{"pnl": 100.0} for _ in range(5)]
    concentrated.extend({"pnl": 1.0} for _ in range(15))

    diagnostics = build_state_surface_forward_tail_diagnostics(concentrated)

    assert diagnostics["read_only"] is True
    assert diagnostics["metrics_for_gates"]["total_trades"] == 20
    assert diagnostics["gate_report"]["passed"] is False
    assert "pnl_top5_concentration" in diagnostics["gate_report"]["hard_failures"]


def test_state_surface_forward_gate_includes_tail_failure_after_sample_matures():
    state = empty_state_surface_sleeve_state()
    state["closed_positions"] = [{"pnl": 100.0} for _ in range(5)]
    state["closed_positions"].extend({"pnl": 1.0} for _ in range(15))

    snapshot = build_state_surface_sleeve_snapshot(
        state_surface_queue={"candidates": [], "candidate_count": 0},
        as_of="2026-05-20",
        state=state,
        persist=False,
    )

    assert snapshot["trade_enabled"] is False
    assert snapshot["forward_paper_gate"]["status"] == "blocked"
    assert "tail_gate" in snapshot["forward_paper_gate"]["reasons"]
    assert "pnl_top5_concentration" in snapshot["tail_diagnostics"]["gate_report"]["hard_failures"]
    assert snapshot["production_impact"]["alters_orders"] is False


def test_report_generator_renders_state_surface_without_orders():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation(),
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
    assert "Tail gate:" in report
