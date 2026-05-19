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


BROAD_BREADTH_DISABLED = {
    "rank_notional_broad_breadth_support_enabled": False,
}


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


def _ohlcv_rank2_ret20_lead():
    rows = _ohlcv_broad_rotation_many()
    rows["AAA"] = _rows(50.0, 0.0020)
    rows["BBB"] = _rows(50.0, 0.00225)
    rows["CCC"] = _rows(50.0, 0.0014)
    rows["DDD"] = _rows(50.0, 0.0012)
    rows["EEE"] = _rows(50.0, 0.0010)
    rows["FFF"] = _rows(50.0, 0.0008)
    rows["AAA"][-1]["volume"] = rows["AAA"][-1]["volume"] * 200
    return rows


def _ohlcv_rank1_ret20_dominance():
    rows = _ohlcv_broad_rotation_many()
    rows["BBB"] = _rows(50.0, 0.0030)
    return rows


def _ohlcv_rank1_ret60_overheat():
    rows = _ohlcv_broad_rotation_many()
    rows["AAA"] = _rows(50.0, 0.0070)
    rows["BBB"] = _rows(50.0, 0.0024)
    rows["CCC"] = _rows(50.0, 0.0022)
    rows["DDD"] = _rows(50.0, 0.0020)
    rows["EEE"] = _rows(50.0, 0.0018)
    rows["FFF"] = _rows(50.0, 0.0016)
    return rows


def _ohlcv_top2_tech_cohesion():
    return {
        "SPY": _rows(100.0, 0.0002),
        "QQQ": _rows(100.0, 0.0003),
        "IWM": _rows(100.0, 0.0020),
        "PLTR": _rows(50.0, 0.0024),
        "CRDO": _rows(50.0, 0.0022),
        "GOOG": _rows(50.0, 0.0018),
        "XOM": _rows(50.0, 0.0016),
        "CVX": _rows(50.0, 0.0014),
        "DIS": _rows(50.0, 0.0012),
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
        2.54375,
        2.578125,
        2.0625,
        0.7425,
        0.385,
    ]
    assert [row["event_notional_usd"] for row in queue["candidates"]] == [
        25437.5,
        25781.25,
        20625.0,
        7425.0,
        3850.0,
    ]
    assert {
        row["rank_notional_profile_name"] for row in queue["candidates"]
    } == {"score_expansion_top3_ge_0p4"}
    assert {row["candidate_breadth"] for row in queue["candidates"]} == {5}
    assert {row["score_top3_spread"] for row in queue["candidates"]} == {0.931526}
    assert queue["candidates"][2]["rank3_near_high_60"] >= 0.98
    assert queue["candidates"][2]["rank3_near_high_support_applied"] is True
    assert queue["candidates"][2]["rank3_near_high_support_base_multiplier"] == 1.0
    assert queue["candidates"][1]["rank2_near_high_60"] >= 0.975
    assert queue["candidates"][1]["rank2_near_high_support_applied"] is True
    assert queue["candidates"][1]["rank2_near_high_support_base_multiplier"] == 1.25
    assert queue["rank_notional_profile"]["rank2_near_high_support_enabled"] is True
    assert queue["rank_notional_profile"]["rank2_near_high_support_min"] == 0.975
    assert queue["rank_notional_profile"]["rank2_near_high_support_scalar"] == 1.5
    assert queue["rank_notional_profile"]["rank3_near_high_support_enabled"] is True
    assert queue["rank_notional_profile"]["rank3_near_high_support_min"] == 0.98
    assert queue["rank_notional_profile"]["rank3_near_high_support_scalar"] == 1.5
    assert queue["rank_notional_profile"]["top3_ret5_followthrough_enabled"] is True
    assert queue["rank_notional_profile"]["top3_ret5_followthrough_min"] == 0.0
    assert queue["rank_notional_profile"]["top3_ret5_followthrough_scalar"] == 1.25
    assert queue["rank_notional_profile"]["top3_ret5_followthrough_max_queue_rank"] == 3
    assert queue["rank_notional_profile"]["broad_breadth_support_enabled"] is True
    assert queue["rank_notional_profile"]["broad_breadth_support_bucket"] == "broad_breadth"
    assert queue["rank_notional_profile"]["broad_breadth_support_scalar"] == 1.1
    assert [
        row["top3_ret5_followthrough_applied"] for row in queue["candidates"]
    ] == [True, True, True, False, False]
    assert [
        row["broad_breadth_support_applied"] for row in queue["candidates"]
    ] == [True, True, True, True, True]
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
    assert queue["rank_notional_profile"]["score_expansion_min_top3_spread"] == 0.40
    assert queue["rank_notional_profile"]["score_expansion_rank_event_notional_usd"] == [
        18500.0,
        12500.0,
        10000.0,
        6750.0,
        3500.0,
    ]
    assert {row["surface"] for row in queue["candidates"]} == {"rotation_breakout_leadership"}
    assert all(row["ret20_excess_spy_gate"]["allowed"] is True for row in queue["candidates"])
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_rank3_near_high_support_persists_to_paper_ledger():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation_many(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
    )

    rank3 = next(row for row in queue["candidates"] if row["queue_rank"] == 3)
    assert rank3["rank3_near_high_60"] >= 0.98
    assert rank3["rank3_near_high_support_applied"] is True
    assert rank3["rank3_near_high_support_scalar"] == 1.5
    assert rank3["rank3_near_high_support_base_multiplier"] == 1.0
    assert rank3["rank_notional_multiplier"] == 1.5
    assert rank3["event_notional_usd"] == 15000.0
    assert {
        row["rank3_near_high_support_applied"]
        for row in queue["candidates"]
        if row["queue_rank"] != 3
    } == {False}

    state = empty_state_surface_sleeve_state()
    first = build_state_surface_sleeve_snapshot(
        state_surface_queue=queue,
        as_of="2026-05-04",
        state=state,
        persist=False,
    )
    pending = next(row for row in first["pending_entries"] if row["queue_rank"] == 3)
    assert pending["rank3_near_high_support_applied"] is True
    assert pending["rank3_near_high_support_scalar"] == 1.5
    assert pending["event_notional_usd"] == 15000.0
    assert pending["candidate"]["rank3_near_high_support_applied"] is True

    next_state = empty_state_surface_sleeve_state()
    next_state["pending_entries"] = first["pending_entries"]
    prices = {row["ticker"]: 100.0 for row in first["pending_entries"]}
    second = build_state_surface_sleeve_snapshot(
        state_surface_queue={"candidates": [], "candidate_count": 0},
        as_of="2026-05-05",
        state=next_state,
        open_prices=prices,
        current_prices=prices,
        persist=False,
    )
    position = next(
        row for row in second["open_positions"] if row["ticker"] == pending["ticker"]
    )
    assert position["rank3_near_high_support_applied"] is True
    assert position["rank3_near_high_support_scalar"] == 1.5
    assert position["rank_notional_multiplier"] == 1.5
    assert position["notional"] == 15000.0
    assert second["trade_enabled"] is False
    assert second["production_impact"]["alters_orders"] is False


def test_state_surface_rank3_volume_confirmation_persists_to_paper_ledger():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation_many(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_rank3_volume_confirmation_min": 0.0,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
    )

    rank3 = next(row for row in queue["candidates"] if row["queue_rank"] == 3)
    assert rank3["rank3_volume_confirmation_applied"] is True
    assert rank3["rank3_volume_confirmation_scalar"] == 1.5
    assert rank3["rank3_volume_confirmation_base_multiplier"] == 1.5
    assert rank3["rank_notional_multiplier"] == 2.25
    assert rank3["event_notional_usd"] == 22500.0
    assert {
        row["rank3_volume_confirmation_applied"]
        for row in queue["candidates"]
        if row["queue_rank"] != 3
    } == {False}
    assert queue["rank_notional_profile"]["rank3_volume_confirmation_enabled"] is True
    assert queue["rank_notional_profile"]["rank3_volume_confirmation_min"] == 0.0
    assert queue["rank_notional_profile"]["rank3_volume_confirmation_scalar"] == 1.5

    state = empty_state_surface_sleeve_state()
    first = build_state_surface_sleeve_snapshot(
        state_surface_queue=queue,
        as_of="2026-05-04",
        state=state,
        persist=False,
    )
    pending = next(row for row in first["pending_entries"] if row["queue_rank"] == 3)
    assert pending["rank3_volume_confirmation_applied"] is True
    assert pending["rank3_volume_confirmation_scalar"] == 1.5
    assert pending["event_notional_usd"] == 22500.0
    assert pending["candidate"]["rank3_volume_confirmation_applied"] is True

    next_state = empty_state_surface_sleeve_state()
    next_state["pending_entries"] = first["pending_entries"]
    prices = {row["ticker"]: 100.0 for row in first["pending_entries"]}
    second = build_state_surface_sleeve_snapshot(
        state_surface_queue={"candidates": [], "candidate_count": 0},
        as_of="2026-05-05",
        state=next_state,
        open_prices=prices,
        current_prices=prices,
        persist=False,
    )
    position = next(
        row for row in second["open_positions"] if row["ticker"] == pending["ticker"]
    )
    assert position["rank3_volume_confirmation_applied"] is True
    assert position["rank3_volume_confirmation_scalar"] == 1.5
    assert position["rank_notional_multiplier"] == 2.25
    assert position["notional"] == 22500.0
    assert second["trade_enabled"] is False
    assert second["production_impact"]["alters_orders"] is False


def test_state_surface_rank2_volume_confirmation_persists_to_paper_ledger():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation_many(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_rank2_volume_confirmation_min": 0.0,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
    )

    rank2 = next(row for row in queue["candidates"] if row["queue_rank"] == 2)
    assert rank2["rank2_volume_confirmation_applied"] is True
    assert rank2["rank2_volume_confirmation_scalar"] == 1.1
    assert rank2["rank2_volume_confirmation_base_multiplier"] == 1.875
    assert rank2["rank_notional_multiplier"] == 2.0625
    assert rank2["event_notional_usd"] == 20625.0
    assert {
        row["rank2_volume_confirmation_applied"]
        for row in queue["candidates"]
        if row["queue_rank"] != 2
    } == {False}
    assert queue["rank_notional_profile"]["rank2_volume_confirmation_enabled"] is True
    assert queue["rank_notional_profile"]["rank2_volume_confirmation_min"] == 0.0
    assert queue["rank_notional_profile"]["rank2_volume_confirmation_scalar"] == 1.1

    state = empty_state_surface_sleeve_state()
    first = build_state_surface_sleeve_snapshot(
        state_surface_queue=queue,
        as_of="2026-05-04",
        state=state,
        persist=False,
    )
    pending = next(row for row in first["pending_entries"] if row["queue_rank"] == 2)
    assert pending["rank2_volume_confirmation_applied"] is True
    assert pending["rank2_volume_confirmation_scalar"] == 1.1
    assert pending["event_notional_usd"] == 20625.0
    assert pending["candidate"]["rank2_volume_confirmation_applied"] is True

    next_state = empty_state_surface_sleeve_state()
    next_state["pending_entries"] = first["pending_entries"]
    prices = {row["ticker"]: 100.0 for row in first["pending_entries"]}
    second = build_state_surface_sleeve_snapshot(
        state_surface_queue={"candidates": [], "candidate_count": 0},
        as_of="2026-05-05",
        state=next_state,
        open_prices=prices,
        current_prices=prices,
        persist=False,
    )
    position = next(
        row for row in second["open_positions"] if row["ticker"] == pending["ticker"]
    )
    assert position["rank2_volume_confirmation_applied"] is True
    assert position["rank2_volume_confirmation_scalar"] == 1.1
    assert position["rank_notional_multiplier"] == 2.0625
    assert position["notional"] == 20625.0
    assert second["trade_enabled"] is False
    assert second["production_impact"]["alters_orders"] is False


def test_state_surface_rank2_near_high_support_persists_to_paper_ledger():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation_many(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
    )

    rank2 = next(row for row in queue["candidates"] if row["queue_rank"] == 2)
    assert rank2["rank2_near_high_60"] >= 0.975
    assert rank2["rank2_near_high_support_applied"] is True
    assert rank2["rank2_near_high_support_scalar"] == 1.5
    assert rank2["rank2_near_high_support_base_multiplier"] == 1.25
    assert rank2["rank_notional_multiplier"] == 1.875
    assert rank2["event_notional_usd"] == 18750.0
    assert {
        row["rank2_near_high_support_applied"]
        for row in queue["candidates"]
        if row["queue_rank"] != 2
    } == {False}

    state = empty_state_surface_sleeve_state()
    first = build_state_surface_sleeve_snapshot(
        state_surface_queue=queue,
        as_of="2026-05-04",
        state=state,
        persist=False,
    )
    pending = next(row for row in first["pending_entries"] if row["queue_rank"] == 2)
    assert pending["rank2_near_high_support_applied"] is True
    assert pending["rank2_near_high_support_scalar"] == 1.5
    assert pending["event_notional_usd"] == 18750.0
    assert pending["candidate"]["rank2_near_high_support_applied"] is True

    next_state = empty_state_surface_sleeve_state()
    next_state["pending_entries"] = first["pending_entries"]
    prices = {row["ticker"]: 100.0 for row in first["pending_entries"]}
    second = build_state_surface_sleeve_snapshot(
        state_surface_queue={"candidates": [], "candidate_count": 0},
        as_of="2026-05-05",
        state=next_state,
        open_prices=prices,
        current_prices=prices,
        persist=False,
    )
    position = next(
        row for row in second["open_positions"] if row["ticker"] == pending["ticker"]
    )
    assert position["rank2_near_high_support_applied"] is True
    assert position["rank2_near_high_support_scalar"] == 1.5
    assert position["rank_notional_multiplier"] == 1.875
    assert position["notional"] == 18750.0
    assert second["trade_enabled"] is False
    assert second["production_impact"]["alters_orders"] is False


def test_state_surface_top3_ret5_followthrough_persists_to_paper_ledger():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation_many(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
    )

    rank1 = next(row for row in queue["candidates"] if row["queue_rank"] == 1)
    assert rank1["features"]["ret5"] > 0.0
    assert rank1["top3_ret5_followthrough_applied"] is True
    assert rank1["top3_ret5_followthrough_scalar"] == 1.25
    assert rank1["top3_ret5_followthrough_base_multiplier"] == 1.85
    assert rank1["broad_breadth_support_applied"] is True
    assert rank1["broad_breadth_support_scalar"] == 1.1
    assert rank1["broad_breadth_support_base_multiplier"] == 2.3125
    assert rank1["rank_notional_multiplier"] == 2.54375
    assert rank1["event_notional_usd"] == 25437.5
    assert [
        row["top3_ret5_followthrough_applied"] for row in queue["candidates"]
    ] == [True, True, True, False, False]

    state = empty_state_surface_sleeve_state()
    first = build_state_surface_sleeve_snapshot(
        state_surface_queue=queue,
        as_of="2026-05-04",
        state=state,
        persist=False,
    )
    pending = next(row for row in first["pending_entries"] if row["queue_rank"] == 1)
    assert pending["top3_ret5_followthrough_applied"] is True
    assert pending["top3_ret5_followthrough_scalar"] == 1.25
    assert pending["broad_breadth_support_applied"] is True
    assert pending["broad_breadth_support_scalar"] == 1.1
    assert pending["event_notional_usd"] == 25437.5
    assert pending["candidate"]["top3_ret5_followthrough_applied"] is True
    assert pending["candidate"]["broad_breadth_support_applied"] is True

    next_state = empty_state_surface_sleeve_state()
    next_state["pending_entries"] = first["pending_entries"]
    prices = {row["ticker"]: 100.0 for row in first["pending_entries"]}
    second = build_state_surface_sleeve_snapshot(
        state_surface_queue={"candidates": [], "candidate_count": 0},
        as_of="2026-05-05",
        state=next_state,
        open_prices=prices,
        current_prices=prices,
        persist=False,
    )
    position = next(
        row for row in second["open_positions"] if row["ticker"] == pending["ticker"]
    )
    assert position["top3_ret5_followthrough_applied"] is True
    assert position["top3_ret5_followthrough_scalar"] == 1.25
    assert position["broad_breadth_support_applied"] is True
    assert position["broad_breadth_support_scalar"] == 1.1
    assert position["rank_notional_multiplier"] == 2.54375
    assert position["notional"] == 25437.5
    assert second["trade_enabled"] is False
    assert second["production_impact"]["alters_orders"] is False


def test_state_surface_broad_breadth_support_persists_to_paper_ledger():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation(),
        universe=["AAA", "BBB", "CCC"],
        config={
            "max_candidates": 1,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
    )

    candidate = queue["candidates"][0]
    assert candidate["breadth_bucket"] == "broad_breadth"
    assert candidate["broad_breadth_support_applied"] is True
    assert candidate["broad_breadth_support_scalar"] == 1.1
    assert candidate["broad_breadth_support_base_multiplier"] == 1.625
    assert candidate["rank_notional_multiplier"] == 1.7875
    assert candidate["event_notional_usd"] == 17875.0
    assert queue["rank_notional_profile"]["broad_breadth_support_enabled"] is True
    assert queue["rank_notional_profile"]["broad_breadth_support_bucket"] == "broad_breadth"
    assert queue["rank_notional_profile"]["broad_breadth_support_scalar"] == 1.1

    state = empty_state_surface_sleeve_state()
    first = build_state_surface_sleeve_snapshot(
        state_surface_queue=queue,
        as_of="2026-05-04",
        state=state,
        persist=False,
    )
    pending = first["pending_entries"][0]
    assert pending["broad_breadth_support_applied"] is True
    assert pending["broad_breadth_support_scalar"] == 1.1
    assert pending["event_notional_usd"] == 17875.0
    assert pending["candidate"]["broad_breadth_support_applied"] is True

    next_state = empty_state_surface_sleeve_state()
    next_state["pending_entries"] = first["pending_entries"]
    ticker = pending["ticker"]
    second = build_state_surface_sleeve_snapshot(
        state_surface_queue={"candidates": [], "candidate_count": 0},
        as_of="2026-05-05",
        state=next_state,
        open_prices={ticker: 100.0},
        current_prices={ticker: 100.0},
        persist=False,
    )
    position = second["open_positions"][0]
    assert position["broad_breadth_support_applied"] is True
    assert position["broad_breadth_support_scalar"] == 1.1
    assert position["rank_notional_multiplier"] == 1.7875
    assert position["notional"] == 17875.0
    assert second["trade_enabled"] is False
    assert second["production_impact"]["alters_orders"] is False


def test_state_surface_queue_can_disable_regime_rank_notional_profile():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation_many(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_regime_profiles_enabled": False,
            "rank_notional_candidate_breadth_profiles_enabled": False,
            "rank_notional_score_expansion_profiles_enabled": False,
            "rank_notional_rank3_near_high_support_enabled": False,
            "rank_notional_rank2_near_high_support_enabled": False,
            "rank_notional_top3_ret5_followthrough_enabled": False,
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
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_candidate_breadth_profiles_enabled": False,
            "rank_notional_score_expansion_profiles_enabled": False,
            "rank_notional_rank3_near_high_support_enabled": False,
            "rank_notional_rank2_near_high_support_enabled": False,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
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
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_score_compression_max_top3_spread": 2.0,
            "rank_notional_rank3_near_high_support_enabled": False,
            "rank_notional_rank2_near_high_support_enabled": False,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
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


def test_state_surface_queue_applies_rank1_score_isolation_before_expansion():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation_many(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_rank1_score_isolation_min_score_gap": 0.0,
            "rank_notional_rank3_near_high_support_enabled": False,
            "rank_notional_rank2_near_high_support_enabled": False,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
    )

    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["candidate_count"] == 5
    assert [row["rank_notional_multiplier"] for row in queue["candidates"]] == [
        2.2,
        1.0,
        0.7,
        0.675,
        0.35,
    ]
    assert [row["event_notional_usd"] for row in queue["candidates"]] == [
        22000.0,
        10000.0,
        7000.0,
        6750.0,
        3500.0,
    ]
    assert {
        row["rank_notional_profile_name"] for row in queue["candidates"]
    } == {"rank1_score_gap_ge_0_score_expansion_top3_ge_0p4"}
    assert {
        row["rank_notional_rank1_score_isolation_rule_version"]
        for row in queue["candidates"]
    } == {"state_surface_rank1_score_isolation_rank_notional_v1"}
    assert queue["rank_notional_profile"][
        "rank1_score_isolation_profiles_enabled"
    ] is True
    assert queue["rank_notional_profile"]["rank1_score_isolation_min_score_gap"] == 0.0
    assert queue["rank_notional_profile"][
        "rank1_score_isolation_rank_event_notional_usd"
    ] == [
        22000.0,
        10000.0,
        7000.0,
        6750.0,
        3500.0,
    ]
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_queue_applies_rank2_ret20_lead_profile_before_score_compression():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_rank2_ret20_lead(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_score_compression_max_top3_spread": 2.0,
            "rank_notional_rank2_ret20_score_gap_profiles_enabled": False,
            "rank_notional_rank3_near_high_support_enabled": False,
            "rank_notional_rank2_near_high_support_enabled": False,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
    )

    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["candidate_count"] == 5
    assert queue["candidates"][0]["ticker"] == "AAA"
    assert queue["candidates"][1]["ticker"] == "BBB"
    assert queue["candidates"][0]["rank2_ret20_excess_spy_lead"] >= 0.005
    assert [row["rank_notional_multiplier"] for row in queue["candidates"]] == [
        1.3,
        1.55,
        1.1,
        0.675,
        0.35,
    ]
    assert {
        row["rank_notional_profile_name"] for row in queue["candidates"]
    } == {"rank2_ret20_lead_ge_0p005"}
    assert queue["rank_notional_profile"]["rank2_ret20_lead_profiles_enabled"] is True
    assert queue["rank_notional_profile"]["rank2_ret20_lead_min"] == 0.005
    assert queue["rank_notional_profile"]["rank2_ret20_lead_rank_event_notional_usd"] == [
        13000.0,
        15500.0,
        11000.0,
        6750.0,
        3500.0,
    ]
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_queue_applies_rank2_ret20_score_gap_profile_before_rank2_lead():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_rank2_ret20_lead(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_score_compression_max_top3_spread": 2.0,
            "rank_notional_rank3_near_high_support_enabled": False,
            "rank_notional_rank2_near_high_support_enabled": False,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
    )

    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["candidate_count"] == 5
    assert queue["candidates"][0]["ticker"] == "AAA"
    assert queue["candidates"][1]["ticker"] == "BBB"
    assert queue["candidates"][0]["rank2_ret20_excess_spy_lead"] >= 0.005
    assert queue["candidates"][0]["score_top_to_second_gap"] >= 0.30
    assert [row["rank_notional_multiplier"] for row in queue["candidates"]] == [
        1.0,
        1.85,
        1.1,
        0.675,
        0.35,
    ]
    assert {
        row["rank_notional_profile_name"] for row in queue["candidates"]
    } == {"rank2_ret20_lead_ge_0p005_score_gap_ge_0p3"}
    assert queue["rank_notional_profile"]["rank2_ret20_score_gap_profiles_enabled"] is True
    assert queue["rank_notional_profile"]["rank2_ret20_score_gap_min"] == 0.30
    assert queue["rank_notional_profile"]["rank2_ret20_score_gap_rank_event_notional_usd"] == [
        10000.0,
        18500.0,
        11000.0,
        6750.0,
        3500.0,
    ]
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_queue_applies_top2_tech_cohesion_before_rank2_score_gap():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_top2_tech_cohesion(),
        universe=["PLTR", "CRDO", "GOOG", "XOM", "CVX", "DIS"],
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_rank1_ret60_residual_min": 0.0,
            "rank_notional_rank2_ret20_score_gap_min": 0.0,
            "rank_notional_rank3_near_high_support_enabled": False,
            "rank_notional_rank2_near_high_support_enabled": False,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
    )

    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["candidate_count"] == 5
    assert queue["candidates"][0]["sector"] == "Technology"
    assert queue["candidates"][0]["rank1_sector"] == "Technology"
    assert queue["candidates"][0]["rank2_sector"] == "Technology"
    assert all(row["top2_sector_cohesion"] is True for row in queue["candidates"])
    assert [row["rank_notional_multiplier"] for row in queue["candidates"]] == [
        1.45,
        1.7,
        1.15,
        0.675,
        0.35,
    ]
    assert {
        row["rank_notional_profile_name"] for row in queue["candidates"]
    } == {"top2_sector_cohesion_technology"}
    assert {
        row["rank_notional_top2_sector_cohesion_rule_version"]
        for row in queue["candidates"]
    } == {"state_surface_top2_sector_cohesion_rank_notional_v1"}
    assert {
        row["rank_notional_rank1_ret60_residual_rule_version"]
        for row in queue["candidates"]
    } == {"state_surface_rank1_ret60_residual_rank_notional_v1"}
    assert queue["rank_notional_profile"][
        "top2_sector_cohesion_profiles_enabled"
    ] is True
    assert queue["rank_notional_profile"]["top2_sector_cohesion_sector"] == "Technology"
    assert queue["rank_notional_profile"][
        "top2_sector_cohesion_rank_event_notional_usd"
    ] == [
        14500.0,
        17000.0,
        11500.0,
        6750.0,
        3500.0,
    ]
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_queue_applies_rank1_ret60_residual_after_top2_priority():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_rank1_ret60_overheat(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_rank2_ret20_score_gap_min": 0.0,
            "rank_notional_rank3_near_high_support_enabled": False,
            "rank_notional_rank2_near_high_support_enabled": False,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
    )

    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["candidate_count"] == 5
    assert queue["candidates"][0]["ticker"] == "AAA"
    assert queue["candidates"][0]["rank1_ret60"] >= 0.50
    assert [row["rank_notional_multiplier"] for row in queue["candidates"]] == [
        1.2,
        1.85,
        1.1,
        0.675,
        0.35,
    ]
    assert {
        row["rank_notional_profile_name"] for row in queue["candidates"]
    } == {"rank1_ret60_ge_0p5"}
    assert {
        row["rank_notional_rank1_ret60_residual_rule_version"]
        for row in queue["candidates"]
    } == {"state_surface_rank1_ret60_residual_rank_notional_v1"}
    assert queue["rank_notional_profile"]["rank1_ret60_residual_profiles_enabled"] is True
    assert queue["rank_notional_profile"]["rank1_ret60_residual_min"] == 0.50
    assert queue["rank_notional_profile"][
        "rank1_ret60_residual_rank_event_notional_usd"
    ] == [
        12000.0,
        18500.0,
        11000.0,
        6750.0,
        3500.0,
    ]
    assert queue["production_impact"]["alters_orders"] is False


def test_state_surface_queue_applies_rank1_ret20_dominance_profile_before_compression():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_rank1_ret20_dominance(),
        universe=["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
        config={
            **BROAD_BREADTH_DISABLED,
            "rank_notional_rank1_ret20_dominance_lead_min": 0.0,
            "rank_notional_rank1_ret20_dominance_score_gap_min": 0.0,
            "rank_notional_score_compression_max_top3_spread": 2.0,
            "rank_notional_rank3_near_high_support_enabled": False,
            "rank_notional_rank2_near_high_support_enabled": False,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
    )

    assert queue["enabled"] is False
    assert queue["trade_enabled"] is False
    assert queue["candidate_count"] == 5
    assert queue["candidates"][0]["ticker"] == "BBB"
    assert queue["candidates"][0]["rank1_ret20_excess_spy"] > queue["candidates"][0][
        "rank2_ret20_excess_spy"
    ]
    assert queue["candidates"][0]["score_top_to_second_gap"] >= 0.0
    assert [row["rank_notional_multiplier"] for row in queue["candidates"]] == [
        1.6,
        1.4,
        1.0,
        0.675,
        0.35,
    ]
    assert {
        row["rank_notional_profile_name"] for row in queue["candidates"]
    } == {"rank1_ret20_dominance_ge_0_score_gap_ge_0"}
    assert {
        row["rank_notional_rank1_ret20_dominance_rule_version"]
        for row in queue["candidates"]
    } == {"state_surface_rank1_ret20_dominance_rank_notional_v1"}
    assert queue["rank_notional_profile"]["rank1_ret20_dominance_profiles_enabled"] is True
    assert queue["rank_notional_profile"]["rank1_ret20_dominance_lead_min"] == 0.0
    assert queue["rank_notional_profile"]["rank1_ret20_dominance_score_gap_min"] == 0.0
    assert queue["rank_notional_profile"][
        "rank1_ret20_dominance_rank_event_notional_usd"
    ] == [
        16000.0,
        14000.0,
        10000.0,
        6750.0,
        3500.0,
    ]
    assert queue["rank_notional_profile"]["trade_enabled_after_profile"] is False
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
        config={
            **BROAD_BREADTH_DISABLED,
            "max_candidates": 1,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
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


def test_state_surface_sleeve_scales_recent_ticker_repeat_without_orders():
    queue = build_state_surface_queue(
        as_of="2026-05-04",
        ohlcv_by_ticker=_ohlcv_broad_rotation(),
        universe=["AAA", "BBB", "CCC"],
        config={
            **BROAD_BREADTH_DISABLED,
            "max_candidates": 1,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
    )
    state = empty_state_surface_sleeve_state()
    state["closed_positions"] = [
        {
            "decision_id": "prior-aaa",
            "ticker": "AAA",
            "source_event_date": "2026-04-01",
            "paper_status": "closed",
            "pnl": 100.0,
        }
    ]

    snapshot = build_state_surface_sleeve_snapshot(
        state_surface_queue=queue,
        as_of="2026-05-04",
        state=state,
        persist=False,
    )

    pending = snapshot["new_pending_entries"][0]
    assert pending["ticker"] == "AAA"
    assert pending["recent_ticker_repeat_notional_applied"] is True
    assert pending["recent_ticker_repeat_days_since_prior"] == 33
    assert pending["recent_ticker_repeat_prior_date"] == "2026-04-01"
    assert pending["recent_ticker_repeat_scalar"] == 1.5
    assert pending["recent_ticker_repeat_base_event_notional_usd"] == 16250.0
    assert pending["event_notional_usd"] == 24375.0
    assert pending["rank_notional_multiplier"] == 2.4375
    assert pending["candidate"]["event_notional_usd"] == 24375.0
    assert pending["candidate"]["recent_ticker_repeat_notional_applied"] is True
    assert snapshot["rank_notional_profile"]["recent_ticker_repeat_scalar"] == 1.5
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["alters_orders"] is False


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
        config={
            "max_candidates": 1,
            "rank_notional_top3_ret5_followthrough_enabled": False,
        },
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


