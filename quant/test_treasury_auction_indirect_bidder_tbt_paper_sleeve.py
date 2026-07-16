from __future__ import annotations

from datetime import date, timedelta

import pytest

from quant import treasury_auction_indirect_bidder_tbt_paper_sleeve as sleeve
from quant.experiments import (
    exp_20260716_002_treasury_auction_indirect_bidder_share_tbt as experiment,
)


def _auction(
    auction_date: str,
    term: str,
    share: float,
    *,
    cusip: str,
    security_term: str | None = None,
    tips: str = "No",
) -> dict:
    total = 100_000_000.0
    return {
        "auction_date": auction_date,
        "result_publication_date": auction_date,
        "result_release_time_et": "13:01",
        "cusip": cusip,
        "security_type": "Note",
        "security_term": security_term or term,
        "original_security_term": term,
        "tips": tips,
        "floating_rate": "No",
        "indirect_bidder_accepted": total * share,
        "total_accepted": total,
    }


def _history(
    term: str,
    *,
    shares: list[float] | None = None,
    prefix: str = "H",
) -> list[dict]:
    values = shares or [0.60] * sleeve.LOOKBACK_AUCTIONS
    start = date(2024, 1, 2)
    return [
        _auction(
            (start + timedelta(days=7 * index)).isoformat(),
            term,
            share,
            cusip=f"{prefix}{index:08d}"[-9:],
        )
        for index, share in enumerate(values)
    ]


def _bars(
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
                "Open": 999.0,
                "High": 1_001.0,
                "Low": 998.0,
                "Close": 1_000.0,
                "Adjusted Open": adjusted_open,
                "Adjusted High": adjusted_open + 1.0,
                "Adjusted Low": adjusted_open - 1.0,
                "Adjusted Close": adjusted_close,
            }
        )
    return rows


def test_current_share_is_excluded_and_future_cannot_change_signal() -> None:
    history = _history("10-Year", shares=[0.50] * 6 + [0.70] * 6, prefix="A")
    current = _auction("2024-04-02", "10-Year", 0.59, cusip="CURRENT01")
    future = _auction("2024-04-09", "10-Year", 0.99, cusip="FUTURE001")

    without_future = sleeve.build_weak_indirect_bidder_events([*history, current])
    with_future = sleeve.build_weak_indirect_bidder_events([*history, current, future])
    frozen = next(row for row in with_future if row["signal_date"] == "2024-04-02")
    trigger = frozen["weak_auctions"][0]

    assert [row["signal_date"] for row in without_future] == ["2024-04-02"]
    assert trigger["current_auction_excluded_from_baseline"] is True
    assert trigger["trailing_12_indirect_bidder_share_median"] == pytest.approx(0.60)
    assert 0.59 not in trigger["lookback_indirect_bidder_accepted_shares"]


def test_reopening_uses_original_term_and_same_day_tenors_merge() -> None:
    records = [
        *_history("2-Year", prefix="B"),
        *_history("5-Year", prefix="C"),
        _auction(
            "2024-04-02",
            "2-Year",
            0.50,
            cusip="TWOWEAK01",
            security_term="1-Year 10-Month",
        ),
        _auction("2024-04-02", "5-Year", 0.40, cusip="FIVEWEAK1"),
        _auction("2024-04-02", "10-Year", 0.20, cusip="TIPDROP01", tips="Yes"),
    ]

    events = sleeve.build_weak_indirect_bidder_events(records)

    assert len(events) == 1
    assert events[0]["auction_count"] == 2
    assert events[0]["tenors"] == ["2-Year", "5-Year"]
    assert events[0]["same_day_merged"] is True
    assert all(
        row["lookback_auction_count"] == 12 for row in events[0]["weak_auctions"]
    )


@pytest.mark.parametrize(
    ("indirect", "total"),
    [(-1.0, 100.0), (101.0, 100.0), (1.0, 0.0), (None, 100.0)],
)
def test_invalid_participant_composition_fails_closed(indirect, total) -> None:
    current = _auction("2024-04-02", "10-Year", 0.50, cusip="CURRENT01")
    current["indirect_bidder_accepted"] = indirect
    current["total_accepted"] = total

    assert sleeve.build_weak_indirect_bidder_events(
        [*_history("10-Year", prefix="D"), current]
    ) == []


@pytest.mark.parametrize(
    "mutation",
    [
        {"original_security_term": "1-Year"},
        {"result_publication_date": None},
        {"result_release_time_et": "16:00"},
        {"result_release_time_et": "not-a-clock"},
    ],
)
def test_tenor_and_publication_clock_contract_fail_closed(mutation: dict) -> None:
    current = _auction("2024-04-02", "10-Year", 0.50, cusip="CURRENT01")
    current.update(mutation)

    assert sleeve.build_weak_indirect_bidder_events(
        [*_history("10-Year", prefix="E"), current]
    ) == []


def test_execution_is_next_open_fifth_close_costed_and_nonoverlapping() -> None:
    sessions = [
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-13",
        "2025-01-14",
    ]
    tbt = _bars(
        sessions,
        entry_date="2025-01-07",
        exit_date="2025-01-13",
        entry=100.0,
        exit_=110.0,
    )
    comparator = _bars(sessions)
    events = [
        {
            "signal_date": "2025-01-06",
            "decision_id": "first",
            "tenors": ["10-Year"],
            "trade_enabled": False,
        },
        {
            "signal_date": "2025-01-07",
            "decision_id": "second",
            "tenors": ["5-Year"],
            "trade_enabled": False,
        },
    ]

    replay = sleeve.replay_weak_indirect_bidder_tbt(
        events,
        tbt,
        {"SPY": comparator, "QQQ": comparator},
        sessions[0],
        sessions[-1],
    )

    assert replay["rule_version"] == sleeve.RULE_VERSION
    assert replay["signals_generated"] == 2
    assert replay["signals_survived"] == 1
    trade = replay["trades"][0]
    assert trade["entry_date"] == "2025-01-07"
    assert trade["exit_date"] == "2025-01-13"
    assert trade["target_price"] == pytest.approx(107.0)
    assert trade["net_return"] == pytest.approx(0.0965)
    assert trade["pnl"] == 1544.0
    assert next(row for row in replay["skipped"] if row["decision_id"] == "second")[
        "reason"
    ] == "max_concurrent_position_one"


def test_snapshot_is_default_off_and_idempotent() -> None:
    sessions = [
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-13",
    ]
    bars = _bars(sessions)
    event = {
        "signal_date": "2025-01-06",
        "decision_id": "weak-share",
        "tenors": ["10-Year"],
        "trade_enabled": False,
    }
    prices = {"TBT": bars, "SPY": bars, "QQQ": bars}

    first = sleeve.build_treasury_auction_indirect_bidder_tbt_snapshot(
        "2025-01-13", [event], prices
    )
    second = sleeve.build_treasury_auction_indirect_bidder_tbt_snapshot(
        "2025-01-13", [event], prices, previous_state=first
    )

    assert first["sleeve"] == sleeve.SLEEVE_NAME
    assert first["rule_version"] == sleeve.RULE_VERSION
    assert first["trade_enabled"] is False
    assert first["orders"] == []
    assert first["closed_trade_count"] == 1
    assert second["closed_trade_count"] == 1
    assert second["closed_count_today"] == 0
    assert second["new_candidate_count"] == 0


def test_standalone_account_is_fully_funded_and_costs_half_open_full_at_exit() -> None:
    dates = ["2025-01-07", "2025-01-08", "2025-01-09"]
    bars = [
        {"date": "2025-01-07", "close": 101.0},
        {"date": "2025-01-08", "close": 105.0},
        {"date": "2025-01-09", "close": 110.0},
    ]
    trade = {
        "entry_date": "2025-01-07",
        "exit_date": "2025-01-09",
        "entry_price": 100.0,
        "pnl": 1_544.0,
    }

    metrics = experiment.account_metrics([trade], dates, bars)

    first_equity = experiment.INITIAL_CAPITAL_USD + sleeve.NOTIONAL_USD * (
        0.01 - sleeve.ROUND_TRIP_COST_PCT / 2.0
    )
    assert metrics["return_series"][0]["return"] == pytest.approx(
        first_equity / experiment.INITIAL_CAPITAL_USD - 1.0
    )
    assert metrics["total_pnl"] == 1_544.0
    assert metrics["max_deployed_notional_usd"] == 16_000.0
    assert metrics["additive_to_core"] is False
