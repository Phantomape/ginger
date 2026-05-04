from __future__ import annotations

from form4_trade_overlap import matching_prior_events


def test_matching_prior_events_respects_lookback_and_direction():
    events = {
        "AMD": [
            {"ticker": "AMD", "usable_trade_date": "2025-05-01"},
            {"ticker": "AMD", "usable_trade_date": "2025-05-20"},
            {"ticker": "AMD", "usable_trade_date": "2025-06-01"},
        ]
    }

    matches = matching_prior_events(events, "AMD", "2025-05-23", 10)

    assert [match["usable_trade_date"] for match in matches] == ["2025-05-20"]
    assert matches[0]["days_before_entry"] == 3
