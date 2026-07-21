from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from quant.senate_lda_regulatory_friction import (
    ACTIVE_SESSIONS,
    ENTRY_SCALAR,
    FROZEN_ISSUER_MAP,
    MIN_ISSUE_BREADTH,
    NEUTRAL_SCALAR,
    PRIOR_NONEMPTY_WEEKS,
    SOURCE,
    TRADE_ENABLED,
    SenateLDAFilingConflictError,
    SenateLDAIndexValidationError,
    SenateLDARegulatoryFrictionResolver,
    build_daily_snapshot,
    build_daily_snapshot_from_resolver,
    build_senate_lda_regulatory_friction_index,
    evaluate_senate_lda_regulatory_friction_weeks,
    normalise_senate_lda_filings,
    normalise_senate_lda_issuer_map,
    senate_lda_client_query_names,
    validate_senate_lda_regulatory_friction_index,
)


def _filing(
    uuid: str,
    posted: str,
    codes: list[str],
    *,
    client_name: str = "Apple Inc.",
    client_effective_date: str = "2023-01-01",
    filing_type_display: str = "Q1 Report",
    client_id: int = 7,
) -> dict[str, object]:
    return {
        "filing_uuid": uuid,
        "dt_posted": posted,
        "filing_type": "Q1",
        "filing_type_display": filing_type_display,
        "client": {
            "id": client_id,
            "name": client_name,
            "effective_date": client_effective_date,
        },
        "lobbying_activities": [
            {"general_issue_code": code} for code in codes
        ],
    }


def _monday_weeks(
    counts: list[int],
    *,
    first_monday: str = "2025-01-06",
    client_name: str = "Apple Inc.",
) -> list[dict[str, object]]:
    start = date.fromisoformat(first_monday)
    rows = []
    for week_index, count in enumerate(counts):
        monday = start + timedelta(days=7 * week_index)
        rows.append(
            _filing(
                f"filing-{week_index}",
                datetime.combine(
                    monday + timedelta(days=2),
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                )
                .replace(hour=16)
                .isoformat()
                .replace("+00:00", "Z"),
                [f"I{week_index}-{code_index}" for code_index in range(count)],
                client_name=client_name,
            )
        )
    return rows


def _business_sessions(start: str, count: int) -> list[str]:
    current = date.fromisoformat(start)
    sessions = []
    while len(sessions) < count:
        if current.weekday() < 5:
            sessions.append(current.isoformat())
        current += timedelta(days=1)
    return sessions


def test_frozen_direct_map_source_constants_and_effective_date_contract():
    assert SOURCE == "senate_lda_quarterly_filings"
    assert TRADE_ENABLED is False
    assert ENTRY_SCALAR == 0.5
    assert ACTIVE_SESSIONS == 10
    assert MIN_ISSUE_BREADTH == 3
    assert PRIOR_NONEMPTY_WEEKS == 4
    assert len(FROZEN_ISSUER_MAP) == 15
    assert set(senate_lda_client_query_names()) == set(FROZEN_ISSUER_MAP)
    rows = {row["ticker"]: row for row in normalise_senate_lda_issuer_map()}
    assert rows["AAPL"]["name_regex"] == r"^APPLE.*\bINC\b"
    assert rows["DE"]["name_regex"] == r"^(?:JOHN\s+)?DEERE\b"
    assert rows["RTX"]["effective_from"] == "2023-07-17"
    assert all(
        row["effective_from"] == "2023-01-01"
        for ticker, row in rows.items()
        if ticker != "RTX"
    )

    before_rename = _filing(
        "rtx-before",
        "2023-07-16T12:00:00Z",
        ["DEF"],
        client_name="RTX Corporation",
    )
    after_rename = _filing(
        "rtx-after",
        "2023-07-17T12:00:00Z",
        ["DEF"],
        client_name="RTX Corporation",
    )
    future_effective = _filing(
        "future-effective",
        "2025-01-08T12:00:00Z",
        ["TEC"],
        client_effective_date="2025-01-09",
    )
    malformed_effective = _filing(
        "malformed-effective",
        "2025-01-08T12:00:00Z",
        ["TEC"],
        client_effective_date="2023-01-01junk",
    )
    normalised = normalise_senate_lda_filings(
        [before_rename, after_rename, future_effective, malformed_effective]
    )
    assert [row["filing_uuid"] for row in normalised] == ["rtx-after"]
    assert normalised[0]["client_name"] == "RTX Corporation"
    assert normalised[0]["client_effective_date"] == "2023-01-01"


def test_only_non_amendment_quarterly_reports_and_dt_posted_is_clock():
    rows = [
        _filing(
            "report",
            "2025-01-08T15:30:00-05:00",
            ["TEC"],
            filing_type_display="1st Quarter - Report",
        ),
        _filing(
            "amendment",
            "2025-01-08T15:30:00Z",
            ["DEF"],
            filing_type_display="1st Quarter - Report (Amendment)",
        ),
        _filing(
            "registration",
            "2025-01-08T15:30:00Z",
            ["TAX"],
            filing_type_display="Registration",
        ),
    ]
    normalised = normalise_senate_lda_filings(rows)
    assert [row["filing_uuid"] for row in normalised] == ["report"]
    assert normalised[0]["dt_posted"] == "2025-01-08T20:30:00Z"
    assert normalised[0]["posted_date"] == "2025-01-08"
    assert normalised[0]["week_start"] == "2025-01-06"
    assert normalised[0]["week_end"] == "2025-01-12"


def test_offset_local_sunday_stays_in_completed_sunday_week():
    row = _filing(
        "sunday-et",
        "2025-02-09T23:30:00-05:00",
        ["TEC"],
        filing_type_display="4th Quarter - Report",
    )
    normalised = normalise_senate_lda_filings([row])
    assert normalised[0]["dt_posted"] == "2025-02-10T04:30:00Z"
    assert normalised[0]["posted_date"] == "2025-02-09"
    assert normalised[0]["week_start"] == "2025-02-03"
    assert normalised[0]["week_end"] == "2025-02-09"


def test_duplicate_uuid_is_deduped_but_conflict_fails_closed():
    row = _filing("same", "2025-01-08T12:00:00Z", ["TEC", "DEF"])
    assert len(normalise_senate_lda_filings([row, dict(row)])) == 1
    changed = dict(row)
    changed["dt_posted"] = "2025-01-09T12:00:00Z"
    with pytest.raises(SenateLDAFilingConflictError, match="same"):
        normalise_senate_lda_filings([row, changed])


def test_completed_week_and_prior_four_nonempty_median_are_strictly_pit():
    filings = _monday_weeks([1, 2, 2, 3, 3])
    # The fifth week ends Sunday 2025-02-09.  It is not complete at the
    # beginning of Sunday, and first becomes evaluable on Monday.
    sunday = evaluate_senate_lda_regulatory_friction_weeks(
        filings, as_of="2025-02-09"
    )
    assert len(sunday["weekly_rows"]) == 4
    assert sunday["trigger_rows"] == []

    monday = evaluate_senate_lda_regulatory_friction_weeks(
        filings, as_of="2025-02-10"
    )
    current = monday["weekly_rows"][-1]
    assert current["week_end"] == "2025-02-09"
    assert current["prior_four_nonempty_issue_breadths"] == [1, 2, 2, 3]
    assert current["prior_four_nonempty_median"] == 2.0
    assert current["issue_breadth"] == 3
    assert current["triggered"] is True
    assert all(
        prior < current["week_start"]
        for prior in current["prior_four_nonempty_week_ends"]
    )

    equal = evaluate_senate_lda_regulatory_friction_weeks(
        _monday_weeks([3, 3, 3, 3, 3]), as_of="2025-02-10"
    )
    assert equal["weekly_rows"][-1]["prior_four_nonempty_median"] == 3.0
    assert equal["weekly_rows"][-1]["triggered"] is False


def test_empty_issue_week_is_not_one_of_prior_four_nonempty_weeks():
    filings = _monday_weeks([1, 0, 2, 2, 3, 4])
    result = evaluate_senate_lda_regulatory_friction_weeks(
        filings, as_of="2025-02-17"
    )
    current = result["weekly_rows"][-1]
    assert current["issue_breadth"] == 4
    assert current["prior_four_nonempty_issue_breadths"] == [1, 2, 2, 3]
    assert current["triggered"] is True


def test_activation_is_first_strictly_later_session_and_exactly_ten_sessions():
    filings = _monday_weeks([1, 2, 2, 3, 4])
    sessions = _business_sessions("2025-02-03", 20)
    index = build_senate_lda_regulatory_friction_index(
        filings,
        sessions,
        source_identity={"request_sha256": "a" * 64, "response_sha256": "b" * 64},
    )
    trigger = index["activated_triggers"][0]
    assert trigger["week_end"] == "2025-02-09"
    assert trigger["activation_session"] == "2025-02-10"
    assert trigger["active_through_session"] == "2025-02-21"
    assert len(trigger["active_sessions"]) == ACTIVE_SESSIONS
    assert index["session_scalars"]["2025-02-07"] == {}
    assert index["session_scalars"]["2025-02-10"] == {"AAPL": ENTRY_SCALAR}
    assert index["session_scalars"]["2025-02-21"] == {"AAPL": ENTRY_SCALAR}
    assert index["session_scalars"]["2025-02-24"] == {}

    resolver = SenateLDARegulatoryFrictionResolver.from_index(index)
    assert resolver.evaluate("2025-02-10", "AAPL")["scalar"] == ENTRY_SCALAR
    assert resolver.evaluate("2025-02-24", "AAPL")["scalar"] == NEUTRAL_SCALAR


def test_hash_binding_rejects_mutation_and_copies_caller_inputs():
    filings = _monday_weeks([1, 2, 2, 3, 4])
    sessions = _business_sessions("2025-02-03", 20)
    resolver = SenateLDARegulatoryFrictionResolver(filings, sessions)
    original = resolver.evaluate("2025-02-10", "AAPL")
    filings[-1]["client"] = {"name": "tampered"}
    sessions[5] = "2099-01-01"
    assert resolver.evaluate("2025-02-10", "AAPL")["decision_hash"] == original[
        "decision_hash"
    ]

    index = resolver.index
    index["session_scalars"]["2025-02-10"]["AAPL"] = 0.9
    with pytest.raises(SenateLDAIndexValidationError, match="index_hash"):
        validate_senate_lda_regulatory_friction_index(index)


def test_missing_and_malformed_source_fail_open_to_neutral_scalar():
    sessions = ["2025-02-10"]
    for rows in (
        None,
        [{"filing_uuid": "bad", "dt_posted": "not-a-date"}],
        [_filing("bad-client", "2025-02-01T12:00:00Z", ["TEC"], client_name="")],
    ):
        resolver = SenateLDARegulatoryFrictionResolver(rows, sessions)
        decision = resolver.evaluate("2025-02-10", "AAPL")
        assert decision["scalar"] == NEUTRAL_SCALAR
        assert decision["active"] is False


def test_daily_snapshot_and_replay_resolver_share_exact_policy_default_off():
    filings = _monday_weeks([1, 2, 2, 3, 4])
    sessions = _business_sessions("2025-02-03", 20)
    source_identity = {"response_sha256": "c" * 64}
    resolver = SenateLDARegulatoryFrictionResolver(
        filings, sessions, source_identity
    )
    replay = resolver.evaluate("2025-02-10", "AAPL")
    snapshot = build_daily_snapshot(
        filings,
        "2025-02-10",
        sessions,
        ["AAPL", "MSFT"],
        source_identity=source_identity,
    )
    reused_snapshot = build_daily_snapshot_from_resolver(
        resolver,
        "2025-02-10",
        ["AAPL", "MSFT"],
    )
    daily = {row["ticker"]: row for row in snapshot["candidates"]}
    assert snapshot["ticker_scalars"] == {"AAPL": 0.5, "MSFT": 1.0}
    assert daily["AAPL"]["decision_hash"] == replay["decision_hash"]
    assert daily["AAPL"]["trigger_rows"] == replay["trigger_rows"]
    assert snapshot["index_hash"] == resolver.metadata["index_hash"]
    assert snapshot["trade_enabled"] is False
    assert snapshot["can_place_orders"] is False
    assert snapshot["orders"] == []
    assert snapshot["order_intents"] == []
    assert reused_snapshot == snapshot
    assert reused_snapshot["snapshot_hash"] == snapshot["snapshot_hash"]
