from datetime import date, datetime
from types import SimpleNamespace

import pytest

from quant.cash_conflict_oldest_rotation import (
    POLICY_VERSION,
    select_oldest_core_incumbent,
)


def _position(ticker, entry_date, sleeve="core", **extra):
    return SimpleNamespace(
        ticker=ticker,
        entry_date=entry_date,
        sleeve=sleeve,
        **extra,
    )


def test_selects_oldest_core_with_ticker_tie_break_and_audit_index():
    positions = [
        _position("MSFT", "2026-07-01"),
        _position("AMZN", "2026-06-01"),
        _position("AAPL", "2026-06-01"),
    ]

    decision = select_oldest_core_incumbent(
        positions,
        "2026-07-15",
        "NVDA",
    )

    assert decision["policy_version"] == POLICY_VERSION
    assert decision["status"] == "selected"
    assert decision["decision"] == "rotate"
    assert decision["reason"] == "oldest_eligible_core_selected"
    assert decision["selected_ticker"] == "AAPL"
    assert decision["selected_entry_date"] == "2026-06-01"
    assert decision["selected_position_index"] == 2
    assert decision["position"] is positions[2]
    assert decision["ticker"] == "AAPL"
    assert decision["entry_date"] == "2026-06-01"
    assert [row["ticker"] for row in decision["eligible_positions"]] == [
        "AAPL",
        "AMZN",
        "MSFT",
    ]


def test_excludes_candidate_future_dated_and_non_core_positions():
    positions = [
        _position("NVDA", "2026-01-01"),
        _position("PAPER", "2026-01-02", sleeve="pilot"),
        _position("FUTR", "2026-07-16"),
        _position("CORE", "2026-07-15"),
    ]

    decision = select_oldest_core_incumbent(
        positions,
        signal_date=date(2026, 7, 15),
        candidate_ticker="nvda",
    )

    assert decision["selected_ticker"] == "CORE"
    assert decision["selected_entry_date"] == "2026-07-15"
    assert decision["eligible_count"] == 1
    assert decision["excluded_counts"] == {
        "candidate_ticker": 1,
        "non_core_sleeve": 1,
        "future_dated": 1,
    }


def test_no_rotation_is_auditable_when_every_position_is_ineligible():
    decision = select_oldest_core_incumbent(
        [
            {"ticker": "NEW", "entry_date": "2026-07-17", "sleeve": "core"},
            {"ticker": "ALT", "entry_date": "2026-01-01", "sleeve": "paper"},
            {"ticker": "MISS", "sleeve": "core"},
        ],
        signal_date=datetime(2026, 7, 16, 20, 0),
        candidate_ticker="NEW",
    )

    assert decision["decision"] == "no_rotation"
    assert decision["status"] == "no_eligible_incumbent"
    assert decision["reason"] == "no_eligible_core_position"
    assert decision["selected_position_index"] is None
    assert decision["selected_ticker"] is None
    assert decision["position"] is None
    assert decision["ticker"] is None
    assert decision["entry_date"] is None
    assert decision["eligible_count"] == 0
    assert decision["considered_count"] == 3
    assert decision["excluded_counts"] == {
        "candidate_ticker": 1,
        "non_core_sleeve": 1,
        "missing_or_invalid_entry_date": 1,
    }


def test_selection_does_not_read_price_or_return_fields():
    class PositionWithoutMarketFields:
        ticker = "OLD"
        entry_date = "2026-01-02"
        sleeve = "core"

        def __getattr__(self, name):
            if name in {"entry_price", "unrealized_return", "relative_return"}:
                raise AssertionError(f"market field unexpectedly read: {name}")
            raise AttributeError(name)

    decision = select_oldest_core_incumbent(
        [PositionWithoutMarketFields()],
        signal_date="2026-07-16T16:00:00Z",
        candidate_ticker="FRESH",
    )

    assert decision["selected_ticker"] == "OLD"


@pytest.mark.parametrize("signal_date", [None, "", "not-a-date", "2026-02-30"])
def test_rejects_invalid_signal_date(signal_date):
    with pytest.raises(ValueError, match="signal_date"):
        select_oldest_core_incumbent(
            [], signal_date=signal_date, candidate_ticker="FRESH"
        )


@pytest.mark.parametrize("candidate_ticker", [None, "", "   "])
def test_rejects_empty_candidate_ticker(candidate_ticker):
    with pytest.raises(ValueError, match="candidate_ticker"):
        select_oldest_core_incumbent(
            [], signal_date="2026-07-16", candidate_ticker=candidate_ticker
        )
