from __future__ import annotations

from form4_skip_oracle_overlap import matching_prior_events


def test_matching_prior_events_filters_by_candidate_date_and_lookback():
    events = {
        "MU": [
            {"ticker": "MU", "usable_trade_date": "2025-12-01"},
            {"ticker": "MU", "usable_trade_date": "2025-12-15"},
            {"ticker": "MU", "usable_trade_date": "2025-12-22"},
        ]
    }

    matches = matching_prior_events(events, "MU", "2025-12-19", 20)

    assert [match["usable_trade_date"] for match in matches] == ["2025-12-01", "2025-12-15"]
    assert [match["days_before_candidate"] for match in matches] == [18, 4]
