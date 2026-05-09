import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from position_intent import (  # noqa: E402
    audit_position_intent_coverage,
    resolve_intended_shares,
)


def test_resolve_intended_shares_prefers_original_signal_size():
    pos = {
        "ticker": "NVDA",
        "shares": 6,
        "original_shares": 10,
        "intended_shares": 12,
    }

    shares, source = resolve_intended_shares(pos)

    assert shares == 10
    assert source == "original_shares"


def test_audit_position_intent_coverage_flags_nonlegacy_missing_fields():
    open_positions = {
        "positions": [
            {"ticker": "LEG", "shares": 10, "opened_by_strategy": "legacy"},
            {"ticker": "FOMO", "shares": 3, "opened_by_strategy": "fomo"},
            {"ticker": "BRK", "shares": 4, "opened_by_strategy": "breakout_long"},
        ]
    }

    audit = audit_position_intent_coverage(open_positions)

    assert audit["non_legacy_positions"] == 2
    assert audit["positions_with_intended_shares"] == 0
    assert audit["coverage_pct"] == 0.0
    assert audit["missing_intended_share_tickers"] == ["FOMO", "BRK"]


def test_audit_position_intent_coverage_reports_underfilled_position():
    open_positions = {
        "positions": [
            {
                "ticker": "NVDA",
                "shares": 6,
                "intended_shares": 10,
                "opened_by_strategy": "trend_long",
            }
        ]
    }

    audit = audit_position_intent_coverage(open_positions)

    assert audit["non_legacy_positions"] == 1
    assert audit["positions_with_intended_shares"] == 1
    assert audit["coverage_pct"] == 1.0
    assert audit["underfilled_positions"] == [
        {
            "ticker": "NVDA",
            "current_shares": 6.0,
            "intended_shares": 10,
            "shortfall_shares": 4.0,
            "source_field": "intended_shares",
        }
    ]
