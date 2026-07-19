from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta

import pytest

from entry_universe_ledger import membership_hash
from ortex_borrow_entry_gate import (
    AVAIL_RATIO5_STRESS,
    COOLDOWN_SESSIONS,
    FEE_DELTA5_STRESS,
    FEE_LEVEL_STRESS,
    LOOKBACK_SESSIONS,
    OrtexBorrowEntryGateError,
    OrtexBorrowEntryUniverseResolver,
    RULE_VERSION,
    TRADE_ENABLED,
    build_daily_entry_admission_snapshot,
    build_ortex_borrow_stress_exclusion_index,
)


def _sessions(count: int = 24) -> list[str]:
    start = date(2025, 1, 1)
    return [(start + timedelta(days=index)).isoformat() for index in range(count)]


def _row(
    sessions: list[str],
    provider_position: int,
    fee: float,
    *,
    ticker: str = "AAPL",
    usable_trade_date: str | None = None,
    block: str = "test_block",
) -> dict:
    return {
        "ticker": ticker,
        "provider_date": sessions[provider_position],
        "usable_trade_date": usable_trade_date or sessions[provider_position + 1],
        "cost_to_borrow_new_pct": fee,
        "historical_block": block,
    }


def test_fixed_exp_20260712_013_constants_and_level_branch() -> None:
    sessions = _sessions()
    rows = [_row(sessions, 0, 0.20), _row(sessions, 1, 1.00)]
    index = build_ortex_borrow_stress_exclusion_index(rows, sessions)

    assert FEE_LEVEL_STRESS == 1.0
    assert FEE_DELTA5_STRESS == 0.25
    assert AVAIL_RATIO5_STRESS == 0.70
    assert LOOKBACK_SESSIONS == 5
    assert COOLDOWN_SESSIONS == 10
    assert RULE_VERSION
    assert TRADE_ENABLED is False
    assert index["transition_count"] == 1
    assert index["by_session"] == {sessions[2]: ["AAPL"]}
    transition = index["transitions"][0]
    assert transition["fee_level_branch_stressed"] is True
    assert transition["prior_non_stressed"] is True
    assert transition["exclusion_session_count"] == 1


def test_missing_availability_keeps_delta_branch_explicitly_unavailable() -> None:
    sessions = _sessions()
    fees = [0.10, 0.10, 0.10, 0.10, 0.10, 0.50]
    index = build_ortex_borrow_stress_exclusion_index(
        [_row(sessions, position, fee) for position, fee in enumerate(fees)],
        sessions,
    )

    final = next(
        row for row in index["observations"] if row["provider_date"] == sessions[5]
    )
    assert final["fee_delta5_pp"] == pytest.approx(0.40)
    assert final["availability_ratio5"] is None
    assert final["alternate_delta_availability_branch_available"] is False
    assert final["alternate_delta_availability_branch_stressed"] is False
    assert final["alternate_branch_missing_fields"] == ["availability"]
    assert final["stressed"] is False
    assert index["transition_count"] == 0
    assert index["policy_field_coverage"]["availability"] is False


def test_transition_state_initializes_false_and_cooldown_uses_fill_sessions() -> None:
    sessions = _sessions()
    fees = {
        0: 0.10,
        1: 1.10,  # eligible transition, fill position 2
        2: 0.10,
        3: 1.20,  # transition suppressed by the ten-session cooldown
        4: 0.10,
        5: 0.10,
        6: 0.10,
        7: 0.10,
        8: 0.10,
        9: 0.10,
        10: 0.10,
        11: 0.10,
        12: 0.10,
        13: 1.30,  # eligible again, fill position 14
    }
    rows = [_row(sessions, position, fee) for position, fee in fees.items()]
    index = build_ortex_borrow_stress_exclusion_index(rows, sessions)

    assert [row["exclusion_session"] for row in index["transitions"]] == [
        sessions[2],
        sessions[14],
    ]
    assert index["suppressed_transition_count"] == 1
    first_only = build_ortex_borrow_stress_exclusion_index(
        [_row(sessions, 0, 5.0)], sessions
    )
    assert first_only["observations"][0]["prior_observed"] is False
    assert first_only["observations"][0]["transition_state_basis"] == (
        "initial_non_stressed_state"
    )
    assert first_only["transition_count"] == 1


def test_missing_session_resets_transition_state_to_non_stressed() -> None:
    sessions = _sessions()
    rows = [
        _row(sessions, 0, 1.10),
        # Positions 1..11 are deliberately missing; frozen code resets the
        # state on each missing caller trading session.
        _row(sessions, 12, 1.20),
    ]
    index = build_ortex_borrow_stress_exclusion_index(rows, sessions)

    assert index["transition_count"] == 2
    second = next(
        row for row in index["transitions"] if row["provider_date"] == sessions[12]
    )
    assert second["prior_observed"] is False
    assert second["transition_state_basis"] == "missing_trading_session_reset"
    assert second["stress_transition"] is True
    assert second["cooldown_eligible"] is True


def test_fee_delta_uses_exact_trading_session_t_minus_five_row() -> None:
    sessions = _sessions()
    rows = [
        _row(sessions, 0, 0.10),
        _row(sessions, 1, 0.40),
        _row(sessions, 2, 0.20),
        _row(sessions, 3, 0.20),
        # Position 4 is missing.  The fifth prior source row for position 6
        # would be position 0, but exact caller-session t-5 is position 1.
        _row(sessions, 5, 0.20),
        _row(sessions, 6, 0.70),
    ]
    index = build_ortex_borrow_stress_exclusion_index(rows, sessions)
    current = next(
        row for row in index["observations"] if row["provider_date"] == sessions[6]
    )

    assert current["lookback_provider_date"] == sessions[1]
    assert current["fee_delta5_pp"] == pytest.approx(0.30)
    assert current["alternate_delta_availability_branch_available"] is False
    assert current["stressed"] is False


def test_strict_usable_date_rejects_same_day_or_non_next_session_rows() -> None:
    sessions = _sessions()
    rows = [
        _row(sessions, 0, 0.10),
        _row(
            sessions,
            1,
            2.00,
            usable_trade_date=sessions[1],
        ),
    ]
    index = build_ortex_borrow_stress_exclusion_index(rows, sessions)

    assert index["valid_row_count"] == 1
    assert index["invalid_row_count"] == 1
    assert index["transition_count"] == 0
    assert index["by_session"] == {}
    assert index["invalid_rows"][0]["reasons"] == [
        "usable_trade_date_not_strict_next_session"
    ]
    assert index["invalid_rows"][0]["expected_usable_trade_date"] == sessions[2]


def test_index_source_calendar_and_content_hashes_are_validated() -> None:
    sessions = _sessions()
    rows = [_row(sessions, 0, 0.10), _row(sessions, 1, 1.10)]
    derived = build_ortex_borrow_stress_exclusion_index(rows, sessions)
    source_hash = derived["source_rows_canonical_hash"]
    index = build_ortex_borrow_stress_exclusion_index(
        rows, sessions, source_rows_sha256=source_hash
    )
    assert index["source_rows_sha256"] == source_hash
    assert index["source_rows_sha256_supplied"] is True
    OrtexBorrowEntryUniverseResolver(
        ["AAPL"], index, sessions, source_rows_sha256=source_hash
    )

    with pytest.raises(
        OrtexBorrowEntryGateError, match="does not match the canonical input rows"
    ):
        build_ortex_borrow_stress_exclusion_index(
            rows, sessions, source_rows_sha256="a" * 64
        )

    tampered = deepcopy(index)
    tampered["by_session"][sessions[2]] = ["AAPL", "MSFT"]
    with pytest.raises(OrtexBorrowEntryGateError, match="index hash mismatch"):
        OrtexBorrowEntryUniverseResolver(["AAPL"], tampered, sessions)
    with pytest.raises(OrtexBorrowEntryGateError, match="source_rows_sha256"):
        OrtexBorrowEntryUniverseResolver(
            ["AAPL"], index, sessions, source_rows_sha256="b" * 64
        )
    with pytest.raises(OrtexBorrowEntryGateError, match="trading_sessions"):
        OrtexBorrowEntryUniverseResolver(["AAPL"], index, sessions[:-1])


def test_resolver_applies_next_fill_exclusion_and_fail_opens_unknown_coverage() -> None:
    sessions = _sessions(8)
    rows = [_row(sessions, 0, 0.10), _row(sessions, 1, 1.10)]
    index = build_ortex_borrow_stress_exclusion_index(rows, sessions)
    resolver = OrtexBorrowEntryUniverseResolver(
        ["AAPL", "MSFT"], index, sessions
    )

    # A position-1 signal fills at position 2 and sees the transition.  The
    # prior signal fills at position 1, before the transition.
    assert resolver(sessions[1]) == {"MSFT"}
    assert resolver(sessions[0]) == {"AAPL", "MSFT"}
    resolved = resolver.resolve(sessions[1])
    assert resolved["membership_hash"] == membership_hash(["MSFT"])
    assert resolved["provenance"]["entry_session"] == sessions[2]
    assert resolved["provenance"]["coverage_status"] == "partial"
    assert resolved["provenance"]["covered_tickers"] == ["AAPL"]
    assert resolved["provenance"]["missing_tickers"] == ["MSFT"]
    assert resolved["provenance"]["missing_policy_fields"] == ["availability"]

    unknown = resolver.resolve(sessions[-1])
    assert unknown["status"] == "resolved"
    assert unknown["tickers"] == ["AAPL", "MSFT"]
    assert unknown["provenance"]["coverage_status"] == (
        "unknown_no_next_trading_session"
    )
    assert unknown["reason"] == "fail_open_unknown_no_next_trading_session"
    assert unknown["provenance"]["missing_source_fields_by_ticker"] == {
        "AAPL": ["cost_to_borrow_new_pct"],
        "MSFT": ["cost_to_borrow_new_pct"],
    }

    # Exercise BacktestEngine's actual provenance validator.
    from quant.backtester import BacktestEngine

    engine = object.__new__(BacktestEngine)
    engine.universe = ["AAPL", "MSFT"]
    engine.entry_universe_resolver = resolver
    eligible, provenance = BacktestEngine._core_entry_universe_as_of(
        engine, sessions[1]
    )
    assert eligible == {"MSFT"}
    assert provenance["source"] == resolved["source"]


def test_daily_snapshot_matches_resolver_and_is_strictly_default_off() -> None:
    sessions = _sessions(8)
    rows = [_row(sessions, 0, 0.10), _row(sessions, 1, 1.10)]
    index = build_ortex_borrow_stress_exclusion_index(rows, sessions)
    resolver = OrtexBorrowEntryUniverseResolver(
        ["AAPL", "MSFT"], index, sessions
    )
    resolved = resolver.resolve(sessions[1])
    daily = build_daily_entry_admission_snapshot(
        rows, sessions[1], sessions, ["AAPL", "MSFT"]
    )

    assert daily["eligible_tickers"] == resolved["tickers"]
    assert daily["excluded_tickers_for_next_session"] == resolved["provenance"][
        "excluded_tickers"
    ]
    assert daily["next_trading_session"] == resolved["provenance"][
        "entry_session"
    ]
    assert daily["coverage_status"] == resolved["provenance"]["coverage_status"]
    assert daily["membership_hash"] == resolved["membership_hash"]
    assert daily["source_hash"] == resolved["source_hash"]
    assert daily["exclusion_index_hash"] == index["index_hash"]
    assert daily["resolver_snapshot_hash"] == resolved["snapshot_sha256"]
    assert daily["resolver_record_hash"] == resolved["record_hash"]
    assert daily["trade_enabled"] is False
    assert daily["strategy_behavior_changed"] is False
    assert daily["alters_live_orders"] is False
    assert all(candidate["trade_enabled"] is False for candidate in daily["candidates"])
