from __future__ import annotations

from datetime import date, timedelta

import pytest

from quant import treasury_auction_weak_demand_tbt_paper_sleeve as sleeve


def _auction(
    auction_date: str,
    term: str,
    ratio: float,
    *,
    cusip: str,
    security_term: str | None = None,
    security_type: str = "Note",
    tips: str = "No",
) -> dict:
    return {
        "auction_date": auction_date,
        "cusip": cusip,
        "security_type": security_type,
        "security_term": security_term or term,
        "original_security_term": term,
        "tips": tips,
        "bid_to_cover_ratio": ratio,
    }


def _history(
    term: str,
    *,
    ratios: list[float] | None = None,
    start: date = date(2024, 1, 2),
    prefix: str = "H",
) -> list[dict]:
    values = ratios or [2.0] * sleeve.LOOKBACK_AUCTIONS
    return [
        _auction(
            (start + timedelta(days=7 * index)).isoformat(),
            term,
            ratio,
            cusip=f"{prefix}{index:08d}"[-9:],
        )
        for index, ratio in enumerate(values)
    ]


def _event(signal_date: str, decision_id: str) -> dict:
    return {
        "signal_date": signal_date,
        "decision_id": decision_id,
        "tenors": ["10-Year"],
        "trade_enabled": False,
    }


def _adjusted_bars(
    dates: list[str],
    *,
    entry_date: str | None = None,
    exit_date: str | None = None,
    entry: float = 100.0,
    exit_: float = 100.0,
) -> list[dict]:
    rows = []
    for day in dates:
        adjusted_open = entry if day == entry_date else 100.0
        adjusted_close = exit_ if day == exit_date else adjusted_open
        rows.append(
            {
                "Date": day,
                "Open": 1_000.0,
                "High": 2_010.0,
                "Low": 990.0,
                "Close": 2_000.0,
                "Adjusted Open": adjusted_open,
                "Adjusted High": adjusted_open + 1.0,
                "Adjusted Low": adjusted_open - 1.0,
                "Adjusted Close": adjusted_close,
            }
        )
    return rows


def test_current_auction_is_excluded_and_future_cannot_change_frozen_signal() -> None:
    history = _history(
        "10-Year",
        ratios=[1.0] * 6 + [3.0] * 6,
        prefix="A",
    )
    current = _auction("2024-04-02", "10-Year", 1.9, cusip="CURRENT01")
    future = _auction("2024-04-09", "10-Year", 100.0, cusip="FUTURE001")

    without_future = sleeve.build_weak_auction_events([*history, current])
    with_future = sleeve.build_weak_auction_events([*history, current, future])
    frozen = next(row for row in with_future if row["signal_date"] == "2024-04-02")

    assert [row["signal_date"] for row in without_future] == ["2024-04-02"]
    assert frozen["weak_auctions"][0]["current_auction_excluded_from_baseline"] is True
    assert frozen["weak_auctions"][0]["trailing_12_bid_to_cover_median"] == 2.0
    assert 1.9 not in frozen["weak_auctions"][0]["lookback_bid_to_cover_ratios"]


def test_reopening_uses_original_security_term_history() -> None:
    history = _history("10-Year", prefix="B")
    reopening = _auction(
        "2024-04-02",
        "10-Year",
        1.8,
        cusip="REOPEN001",
        security_term="9-Year 10-Month",
    )

    events = sleeve.build_weak_auction_events([*history, reopening])

    assert len(events) == 1
    assert events[0]["tenors"] == ["10-Year"]
    assert events[0]["weak_auctions"][0]["lookback_auction_count"] == 12


def test_same_day_weak_tenors_merge_to_one_signal_and_non_nominal_rows_drop() -> None:
    records = [
        *_history("2-Year", prefix="C"),
        *_history("5-Year", prefix="D"),
        _auction("2024-04-02", "2-Year", 1.8, cusip="TWOWEAK01"),
        _auction("2024-04-02", "5-Year", 1.7, cusip="FIVEWEAK1"),
        _auction(
            "2024-04-02",
            "10-Year",
            1.0,
            cusip="TIPDROP01",
            tips="Yes",
        ),
        _auction(
            "2024-04-02",
            "2-Year",
            1.0,
            cusip="FRNDROP01",
            security_type="FRN",
        ),
    ]

    events = sleeve.build_weak_auction_events(records)

    assert len(events) == 1
    assert events[0]["auction_count"] == 2
    assert events[0]["tenors"] == ["2-Year", "5-Year"]
    assert events[0]["same_day_merged"] is True


def test_consecutive_events_do_not_overlap_the_single_tbt_slot() -> None:
    sessions = [
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-13",
        "2025-01-14",
        "2025-01-15",
    ]
    bars = _adjusted_bars(sessions)
    replay = sleeve.replay_weak_auction_tbt(
        [_event("2025-01-06", "first"), _event("2025-01-07", "second")],
        bars,
        {"SPY": bars, "QQQ": bars},
        "2025-01-06",
        "2025-01-15",
    )

    assert replay["signals_generated"] == 2
    assert replay["signals_survived"] == 1
    assert replay["trades"][0]["decision_id"] == "first"
    assert next(row for row in replay["skipped"] if row["decision_id"] == "second")[
        "reason"
    ] == "max_concurrent_position_one"


def test_strict_next_open_fifth_session_close_cost_and_replacements() -> None:
    sessions = [
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-13",
    ]
    tbt = _adjusted_bars(
        sessions,
        entry_date="2025-01-07",
        exit_date="2025-01-13",
        entry=100.0,
        exit_=110.0,
    )
    spy = _adjusted_bars(
        sessions,
        entry_date="2025-01-07",
        exit_date="2025-01-13",
        entry=100.0,
        exit_=102.0,
    )
    qqq = _adjusted_bars(
        sessions,
        entry_date="2025-01-07",
        exit_date="2025-01-13",
        entry=100.0,
        exit_=104.0,
    )

    replay = sleeve.replay_weak_auction_tbt(
        [_event("2025-01-06", "weak")],
        tbt,
        {"SPY": spy, "QQQ": qqq},
        "2025-01-06",
        "2025-01-13",
    )
    trade = replay["trades"][0]

    assert trade["entry_date"] == "2025-01-07"
    assert trade["exit_date"] == "2025-01-13"
    assert trade["hold_sessions_realized"] == 5
    assert trade["target_price"] == pytest.approx(107.0)
    assert trade["target_price_atr_as_of"] == "2025-01-06"
    assert trade["entry_price"] == 100.0
    assert trade["exit_price"] == 110.0
    assert trade["net_return"] == pytest.approx(0.0965)
    assert trade["round_trip_cost_usd"] == 56.0
    assert trade["pnl"] == 1544.0
    assert trade["cash_replacement_usd"] == 1544.0
    assert trade["spy_replacement_usd"] == 1224.0
    assert trade["qqq_replacement_usd"] == 904.0
    assert trade["tenors"] == ["10-Year"]


def test_raw_prices_are_not_used_in_place_of_adjusted_prices() -> None:
    sessions = [
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-13",
    ]
    adjusted = _adjusted_bars(sessions)
    raw_only = [
        {"Date": row["Date"], "Open": 100.0, "Close": 101.0} for row in adjusted
    ]

    replay = sleeve.replay_weak_auction_tbt(
        [_event("2025-01-06", "weak")],
        raw_only,
        {"SPY": adjusted, "QQQ": adjusted},
        "2025-01-06",
        "2025-01-13",
    )

    assert replay["trades"] == []
    assert replay["skipped"][0]["reason"] == (
        "missing_aligned_adjusted_tbt_or_comparator_bar"
    )


def test_explicit_adjusted_runner_rows_are_accepted() -> None:
    sessions = [
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-13",
    ]
    rows = [
        {
            "date": day,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "adjusted": True,
            "price_basis": "split_and_distribution_adjusted",
        }
        for day in sessions
    ]

    replay = sleeve.replay_weak_auction_tbt(
        [_event("2025-01-06", "runner-row")],
        rows,
        {"SPY": rows, "QQQ": rows},
        "2025-01-06",
        "2025-01-13",
    )

    assert replay["signals_survived"] == 1
    assert replay["trades"][0]["target_price"] == pytest.approx(107.0)


def test_daily_snapshot_is_default_off_pure_and_idempotent() -> None:
    sessions = [
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-13",
    ]
    bars = _adjusted_bars(sessions)
    event = _event("2025-01-06", "weak")
    prices = {"TBT": bars, "SPY": bars, "QQQ": bars}

    first = sleeve.build_treasury_auction_tbt_snapshot(
        "2025-01-13", [event], prices
    )
    second = sleeve.build_treasury_auction_tbt_snapshot(
        "2025-01-13", [event], prices, previous_state=first
    )

    assert first["trade_enabled"] is False
    assert first["orders"] == []
    assert first["closed_trade_count"] == 1
    assert second["closed_trade_count"] == 1
    assert second["closed_count_today"] == 0
    assert second["new_candidate_count"] == 0
    assert second["production_impact"]["alters_orders"] is False
