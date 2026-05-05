from __future__ import annotations

import pytest

from experiments.exp_20260504_010_sec_event_sleeve_backtest import simulate_sleeve


def _row(date: str, open_price: float, close_price: float) -> dict[str, float | str]:
    return {"date": date, "open": open_price, "close": close_price}


def _price_map() -> dict[str, list[dict[str, float | str]]]:
    dates = ["2026-01-02", "2026-01-05", "2026-01-06"]
    return {
        "SPY": [_row(date, 100.0, 100.0) for date in dates],
        "AAA": [
            _row("2026-01-02", 100.0, 101.0),
            _row("2026-01-05", 101.0, 110.0),
            _row("2026-01-06", 110.0, 110.0),
        ],
        "BBB": [
            _row("2026-01-02", 50.0, 50.5),
            _row("2026-01-05", 50.5, 55.0),
            _row("2026-01-06", 55.0, 55.0),
        ],
    }


def _candidate(ticker: str, reaction_excess_return: float) -> dict[str, object]:
    return {
        "ticker": ticker,
        "window": "unit",
        "accession_number": f"{ticker}-accession",
        "entry_date": "2026-01-02",
        "reaction_excess_return": reaction_excess_return,
        "reaction_bucket": "negative_excess",
        "language_score": -2,
        "negative_phrase_hits": ["decline"],
    }


def test_simulate_sleeve_prioritizes_most_negative_reaction_when_slot_is_full() -> None:
    result = simulate_sleeve(
        [_candidate("BBB", -0.01), _candidate("AAA", -0.03)],
        _price_map(),
        holding_days=2,
        max_positions=1,
        initial_capital=1_000.0,
        round_trip_cost_pct=0.01,
    )

    assert result["trade_count"] == 1
    assert result["trades"][0]["ticker"] == "AAA"
    assert result["trades"][0]["exit_date"] == "2026-01-05"
    assert result["trades"][0]["net_return_pct"] == pytest.approx(0.089)
    assert result["final_equity"] == pytest.approx(1_089.0)
    assert result["skipped_count"] == 1
    assert result["skipped_by_reason"] == {"slot_full": 1}
    assert result["skipped_events"][0]["ticker"] == "BBB"


def test_simulate_sleeve_takes_both_same_day_events_when_capacity_allows() -> None:
    result = simulate_sleeve(
        [_candidate("BBB", -0.01), _candidate("AAA", -0.03)],
        _price_map(),
        holding_days=2,
        max_positions=2,
        initial_capital=1_000.0,
        round_trip_cost_pct=0.01,
    )

    assert result["trade_count"] == 2
    assert [trade["ticker"] for trade in result["trades"]] == ["AAA", "BBB"]
    assert result["skipped_count"] == 0
    assert result["final_equity"] == pytest.approx(1_089.0)
