from __future__ import annotations

import datetime as dt

from quant.dividend_restart_bundle_contract import allocate_comparators
from quant.dividend_restart_research import (
    UTC,
    assess_filing,
    decision_ready_at,
    first_trade_session_after_publication,
)


def test_clean_recurring_initiation_is_admitted() -> None:
    result = assess_filing(
        text=(
            "The board approved the initiation of a recurring quarterly cash "
            "dividend program. The initial dividend is $0.14 per share."
        ),
        cash_amount="0.14",
        form_type="8-K",
        item_codes=["8.01", "9.01"],
    )
    assert result.lifecycle_class == "recurring_initiation"
    assert result.amount_match is True
    assert result.confounds == ()
    assert result.strict_clean is True


def test_results_release_is_a_coannouncement_bundle() -> None:
    result = assess_filing(
        text=(
            "Third quarter financial results. The company reinstates its "
            "quarterly cash dividend of $0.10 per share."
        ),
        cash_amount="0.1",
        form_type="8-K",
        item_codes=["2.02", "9.01"],
    )
    assert result.lifecycle_class == "recurring_resumption"
    assert result.amount_match is True
    assert "earnings_filing" in result.confounds
    assert result.strict_clean is False


def test_publication_clock_uses_same_day_only_before_open() -> None:
    sessions = ["2025-04-30", "2025-05-01", "2025-05-02"]
    premarket = dt.datetime(2025, 4, 30, 12, 5, 41, tzinfo=UTC)
    after_open = dt.datetime(2025, 4, 30, 15, 0, 0, tzinfo=UTC)
    assert first_trade_session_after_publication(premarket, sessions) == "2025-04-30"
    assert first_trade_session_after_publication(after_open, sessions) == "2025-05-01"


def test_decision_clock_waits_for_declaration_close_features() -> None:
    accepted = dt.datetime(2025, 4, 30, 12, 5, 41, tzinfo=UTC)
    ready = decision_ready_at(accepted, "2025-04-30")
    sessions = ["2025-04-30", "2025-05-01", "2025-05-02"]
    assert first_trade_session_after_publication(ready, sessions) == "2025-05-01"


def test_amount_must_match_same_filing() -> None:
    result = assess_filing(
        text="The company initiated a quarterly cash dividend of $0.25 per share.",
        cash_amount="0.14",
        form_type="8-K",
        item_codes=["8.01"],
    )
    assert result.lifecycle_class == "recurring_initiation"
    assert result.amount_match is False
    assert result.strict_clean is False


def test_comparator_allocation_releases_slot_after_roster_shrink() -> None:
    hashes = {"core_projection": "a" * 64}
    rows = [
        {
            "decision_key": "SOBO:2024-11-07",
            "ticker": "SOBO",
            "declaration_date": "2024-11-07",
            "entry_session": "2024-11-08",
        }
    ]
    slots = [
        {
            "core_slot_id": "APP:2024-11-08:249.2100",
            "ticker": "APP",
            "entry_date": "2024-11-08",
            "gate1_window": "old_thin",
        }
    ]

    allocation = allocate_comparators(
        rows, slots, allocator_input_hashes=hashes
    )

    assert allocation[0]["comparator_kind"] == "core_slot"
    assert allocation[0]["core_slot_id"] == "APP:2024-11-08:249.2100"
    assert allocation[0]["collision_reason"] is None
