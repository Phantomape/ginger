from __future__ import annotations

import copy
from datetime import date, timedelta

import pytest

from quant import tsa_checkpoint_throughput_paper_sleeve as sleeve


def _source_record(
    *,
    week_ending: str,
    report_date: str,
    knowledge_date: str | None = None,
    weekly_total: float,
    comparison_total: float,
    sha: str = "a" * 64,
) -> dict:
    comparison_week = (
        date.fromisoformat(week_ending) - timedelta(days=364)
    ).isoformat()
    return {
        "week_ending": week_ending,
        "report_date": report_date,
        "knowledge_date": knowledge_date or report_date,
        "weekly_total": weekly_total,
        "comparison_week_ending": comparison_week,
        "prior_year_weekly_total": comparison_total,
        "source_url": (
            "https://www.tsa.gov/foia/readingroom/"
            f"checkpoint-throughput-{week_ending}.pdf"
        ),
        "source_sha256": sha,
    }


def _records() -> list[dict]:
    # Prior report YoY = +10%; current report YoY = +20%, so only the current
    # report has both a preceding-report YoY and strictly positive acceleration.
    return [
        _source_record(
            week_ending="2024-12-27",
            report_date="2024-12-30",
            weekly_total=110.0,
            comparison_total=100.0,
            sha="a" * 64,
        ),
        _source_record(
            week_ending="2025-01-03",
            report_date="2025-01-06",
            weekly_total=120.0,
            comparison_total=100.0,
            sha="b" * 64,
        ),
    ]


def _business_bars(
    start: str = "2024-11-25",
    count: int = 65,
    *,
    slope: float = 0.4,
) -> list[dict]:
    day = date.fromisoformat(start)
    rows = []
    while len(rows) < count:
        if day.weekday() < 5:
            index = len(rows)
            close = 100.0 + slope * index
            rows.append(
                {
                    "date": day.isoformat(),
                    "open": close - 0.2,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                }
            )
        day += timedelta(days=1)
    return rows


def _bars() -> dict[str, list[dict]]:
    output = {"SPY": _business_bars(slope=0.1)}
    for index, ticker in enumerate(sleeve.TRAVEL_BASKET_V1):
        output[ticker] = _business_bars(slope=0.2 + index * 0.01)
    return output


def _current_evaluation(records: list[dict] | None = None) -> dict:
    evaluations, audit = sleeve.evaluate_tsa_checkpoint_throughput_events(
        records or _records()
    )
    assert audit["measurement_valid"] is True
    return next(row for row in evaluations if row["week_ending"] == "2025-01-03")


def test_policy_constants_are_exact_and_default_off() -> None:
    assert sleeve.TRAVEL_BASKET_V1 == (
        "AAL",
        "ABNB",
        "ALK",
        "BKNG",
        "CPA",
        "DAL",
        "EXPE",
        "HLT",
        "LUV",
        "MAR",
        "SKYW",
        "TNL",
        "UAL",
        "VAC",
    )
    assert len(set(sleeve.TRAVEL_BASKET_V1)) == 14
    assert sleeve.LEG_NOTIONAL_USD == 1_000.0
    assert sleeve.EVENT_NOTIONAL_USD == 14_000.0
    assert sleeve.HOLD_SESSIONS == 5
    assert sleeve.COOLDOWN_SESSIONS == 0
    assert sleeve.ROUND_TRIP_COST_PCT == pytest.approx(0.0035)
    assert sleeve.TRADE_ENABLED is False


def test_signal_uses_exact_364_day_yoy_and_strict_positive_acceleration() -> None:
    event = _current_evaluation()
    assert event["comparison_week_ending"] == "2024-01-05"
    assert event["yoy_growth"] == pytest.approx(0.20)
    assert event["prior_report_yoy_growth"] == pytest.approx(0.10)
    assert event["yoy_acceleration"] == pytest.approx(0.10)
    assert event["triggered"] is True

    equal_yoy = _records()
    equal_yoy[-1]["weekly_total"] = 110.0
    event = _current_evaluation(equal_yoy)
    assert event["yoy_growth"] == pytest.approx(0.10)
    assert event["yoy_acceleration"] == pytest.approx(0.0)
    assert event["triggered"] is False
    assert event["filter_reason"] == (
        "weekly_yoy_acceleration_not_strictly_positive"
    )

    zero_yoy = _records()
    zero_yoy[-1]["weekly_total"] = 100.0
    event = _current_evaluation(zero_yoy)
    assert event["yoy_growth"] == pytest.approx(0.0)
    assert event["triggered"] is False
    assert event["filter_reason"] == "weekly_yoy_not_strictly_positive"


def test_source_contract_rejects_wrong_comparison_missing_hash_and_duplicates() -> None:
    wrong_comparison = _records()
    wrong_comparison[-1]["comparison_week_ending"] = "2024-01-04"
    evaluations, audit = sleeve.evaluate_tsa_checkpoint_throughput_events(
        wrong_comparison
    )
    assert evaluations == []
    assert audit["measurement_valid"] is False
    assert "comparison_not_exact_364_days" in audit["source_contract_errors"][0]

    missing_hash = _records()
    missing_hash[-1].pop("source_sha256")
    evaluations, audit = sleeve.evaluate_tsa_checkpoint_throughput_events(
        missing_hash
    )
    assert evaluations == []
    assert audit["measurement_valid"] is False
    assert "source_sha256_missing_or_invalid" in audit["source_contract_errors"][0]

    duplicate = [*_records(), copy.deepcopy(_records()[-1])]
    evaluations, audit = sleeve.evaluate_tsa_checkpoint_throughput_events(duplicate)
    assert evaluations == []
    assert audit["measurement_valid"] is False
    assert "duplicate_week_ending" in audit["source_contract_errors"][0]


def test_candidate_is_one_event_with_exact_14_legs_next_open_and_atr_metadata() -> None:
    candidates, audit = sleeve.build_tsa_checkpoint_throughput_candidates(
        records=_records(),
        ohlcv_by_ticker=_bars(),
        start="2025-01-01",
        end="2025-01-31",
    )
    assert audit["signals_generated"] == 1
    assert audit["signals_survived"] == 1
    assert audit["survival_rate"] == 1.0
    assert audit["selected_event_count"] == 1
    assert audit["selected_leg_count"] == 14
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["report_date"] == "2025-01-06"
    assert candidate["entry_date"] == "2025-01-07"
    assert candidate["entry_date"] > candidate["report_date"]
    assert candidate["eligible_tickers"] == list(sleeve.TRAVEL_BASKET_V1)
    assert candidate["eligible_leg_count"] == 14
    assert candidate["event_notional_usd"] == 14_000.0
    assert {row["paper_notional_usd"] for row in candidate["legs"]} == {
        1_000.0
    }
    assert all(row["target_price"] > row["entry_price"] for row in candidate["legs"])
    assert all("ATR_metadata_only" in row["target_price_role"] for row in candidate["legs"])
    assert all(row["trade_enabled"] is False for row in candidate["legs"])


def test_missing_one_entry_or_atr_bar_fails_closed_without_redistribution() -> None:
    bars = _bars()
    bars["AAL"] = [row for row in bars["AAL"] if row["date"] != "2025-01-07"]
    candidates, audit = sleeve.build_tsa_checkpoint_throughput_candidates(
        records=_records(),
        ohlcv_by_ticker=bars,
        start="2025-01-01",
        end="2025-01-31",
    )
    assert candidates == []
    assert audit["signals_generated"] == 1
    assert audit["signals_survived"] == 0
    assert audit["missed_events"][0]["paper_status"] == "missed"
    assert audit["missed_events"][0]["missing_legs"] == [
        {"ticker": "AAL", "reason": "missing_exact_entry_open"}
    ]

    bars = _bars()
    # Remove one of the exact 14 sessions required by the PIT ATR sentinel.
    bars["ABNB"] = [row for row in bars["ABNB"] if row["date"] != "2025-01-03"]
    candidates, audit = sleeve.build_tsa_checkpoint_throughput_candidates(
        records=_records(),
        ohlcv_by_ticker=bars,
        start="2025-01-01",
        end="2025-01-31",
    )
    assert candidates == []
    assert audit["signals_survived"] == 0
    assert audit["missed_events"][0]["missing_legs"][0]["ticker"] == "ABNB"
    assert "missing_atr_bar" in audit["missed_events"][0]["missing_legs"][0]["reason"]


def test_replay_exits_only_at_fifth_session_close_and_charges_35bps_once() -> None:
    bars = _bars()
    # Every intrahold high exceeds any plausible ATR target. The target remains
    # metadata and must never alter the locked time exit.
    for ticker in sleeve.TRAVEL_BASKET_V1:
        for row in bars[ticker]:
            if "2025-01-07" <= row["date"] <= "2025-01-13":
                row["high"] = 1_000.0

    replay = sleeve.replay_tsa_checkpoint_throughput_paper_trades(
        records=_records(),
        ohlcv_by_ticker=bars,
        start="2025-01-01",
        end="2025-01-31",
    )
    assert replay["signals_generated"] == 1
    assert replay["signals_survived"] == 1
    assert replay["settled_event_count"] == 1
    assert replay["settled_leg_count"] == 14
    assert replay["open_events"] == []
    assert replay["missed_events"] == []
    assert replay["orders"] == []
    assert replay["trade_enabled"] is False
    assert {row["exit_date"] for row in replay["trades"]} == {"2025-01-13"}
    assert {row["exit_reason"] for row in replay["trades"]} == {
        "scheduled_fifth_session_close"
    }
    assert {row["hold_sessions_realized"] for row in replay["trades"]} == {5}

    aal = next(row for row in replay["trades"] if row["ticker"] == "AAL")
    expected_return = (
        aal["exit_price"] / aal["entry_price"]
        - 1.0
        - sleeve.ROUND_TRIP_COST_PCT
    )
    assert aal["pnl_pct_net"] == pytest.approx(expected_return, abs=1e-10)
    assert aal["pnl"] == pytest.approx(1_000.0 * expected_return, abs=0.01)
    assert "ATR_metadata_only" in aal["target_price_role"]
    assert replay["event_trades"][0]["pnl"] == pytest.approx(
        sum(row["pnl"] for row in replay["trades"]), abs=0.01
    )


def test_missing_one_holding_bar_makes_whole_event_missed() -> None:
    bars = _bars()
    bars["VAC"] = [row for row in bars["VAC"] if row["date"] != "2025-01-09"]
    replay = sleeve.replay_tsa_checkpoint_throughput_paper_trades(
        records=_records(),
        ohlcv_by_ticker=bars,
        start="2025-01-01",
        end="2025-01-31",
    )
    assert replay["signals_survived"] == 1
    assert replay["trades"] == []
    assert replay["event_trades"] == []
    assert len(replay["missed_events"]) == 1
    missed = replay["missed_events"][0]
    assert missed["paper_status"] == "missed"
    assert missed["missing_bars"] == [
        {
            "ticker": "VAC",
            "date": "2025-01-09",
            "missing_fields": ["open", "high", "low", "close"],
        }
    ]


def test_daily_snapshot_tracks_pending_open_closed_and_is_idempotent() -> None:
    records = _records()
    bars = _bars()
    release = sleeve.build_tsa_checkpoint_throughput_paper_sleeve_snapshot(
        as_of_date="2025-01-06",
        records=records,
        ohlcv_by_ticker=bars,
    )
    assert release["candidate_count"] == 0
    assert release["pending_count"] == 1
    assert release["pending_events"][0]["week_ending"] == "2025-01-03"
    assert release["open_position_count"] == 0
    assert release["closed_count_today"] == 0
    assert release["missed_count"] == 0

    entry = sleeve.build_tsa_checkpoint_throughput_paper_sleeve_snapshot(
        as_of_date="2025-01-07",
        records=records,
        ohlcv_by_ticker=bars,
        state=release["state"],
    )
    assert entry["candidate_count"] == 1
    assert entry["pending_count"] == 0
    assert entry["open_position_count"] == 1
    assert entry["candidates"][0]["entry_date"] == "2025-01-07"
    assert entry["orders"] == []
    assert entry["trade_enabled"] is False

    duplicate = sleeve.build_tsa_checkpoint_throughput_paper_sleeve_snapshot(
        as_of_date="2025-01-07",
        records=records,
        ohlcv_by_ticker=bars,
        state=entry["state"],
    )
    assert duplicate["candidate_count"] == 0
    assert duplicate["open_position_count"] == 1
    assert duplicate["state"] == entry["state"]

    closed = sleeve.build_tsa_checkpoint_throughput_paper_sleeve_snapshot(
        as_of_date="2025-01-13",
        records=records,
        ohlcv_by_ticker=bars,
        state=entry["state"],
    )
    assert closed["candidate_count"] == 0
    assert closed["open_position_count"] == 0
    assert closed["closed_count_today"] == 1
    assert closed["closed_event_count"] == 1
    assert closed["closed_today"][0]["exit_date"] == "2025-01-13"
    assert len(closed["closed_today"][0]["trades"]) == 14


def test_daily_snapshot_records_missed_entry_and_ignores_future_malformed_source() -> None:
    records = _records()
    future = _source_record(
        week_ending="2025-01-17",
        report_date="2025-01-20",
        weekly_total=130.0,
        comparison_total=100.0,
        sha="not-a-hash",
    )
    bars = _bars()
    valid = sleeve.build_tsa_checkpoint_throughput_paper_sleeve_snapshot(
        as_of_date="2025-01-13",
        records=[*records, future],
        ohlcv_by_ticker=bars,
    )
    assert valid["status"] == "ok"
    assert valid["closed_event_count"] == 1
    assert valid["missed_count"] == 0

    missing_entry = _bars()
    missing_entry["CPA"] = [
        row for row in missing_entry["CPA"] if row["date"] != "2025-01-07"
    ]
    missed = sleeve.build_tsa_checkpoint_throughput_paper_sleeve_snapshot(
        as_of_date="2025-01-07",
        records=records,
        ohlcv_by_ticker=missing_entry,
    )
    assert missed["candidate_count"] == 0
    assert missed["open_position_count"] == 0
    assert missed["missed_count"] == 1
    assert missed["new_missed_count"] == 1
    assert missed["missed_events"][0]["missing_legs"] == [
        {"ticker": "CPA", "reason": "missing_exact_entry_open"}
    ]


def test_batch_modified_stale_report_is_counted_but_never_retro_entered() -> None:
    records = _records()
    # The report's intended opportunity was the 2025-01-07 open, but the
    # conservative observed/Last-Modified date is a week later. A historical
    # batch modification must not manufacture a retroactive entry.
    records[-1]["knowledge_date"] = "2025-01-13"
    replay = sleeve.replay_tsa_checkpoint_throughput_paper_trades(
        records=records,
        ohlcv_by_ticker=_bars(),
        start="2025-01-01",
        end="2025-01-10",
    )
    assert replay["signals_generated"] == 1
    assert replay["signals_survived"] == 0
    assert replay["survival_rate"] == 0.0
    assert replay["selected_candidates"] == []
    assert replay["trades"] == []
    assert replay["event_trades"] == []
    assert len(replay["missed_events"]) == 1
    missed = replay["missed_events"][0]
    assert missed["status"] == "missed_fail_closed_late_discovery"
    assert missed["intended_entry_date"] == "2025-01-07"
    assert missed["first_available_entry_date"] == "2025-01-14"
    assert missed["entry_date"] is None
    assert missed["late_discovery"] is True
    assert replay["reject_totals"]["missed_fail_closed_late_discovery"] == 1


def test_daily_snapshot_waits_for_knowledge_then_records_late_discovery() -> None:
    records = _records()
    records[-1]["knowledge_date"] = "2025-01-13"
    bars = _bars()

    before_knowledge = sleeve.build_tsa_checkpoint_throughput_paper_sleeve_snapshot(
        as_of_date="2025-01-10",
        records=records,
        ohlcv_by_ticker=bars,
    )
    assert before_knowledge["candidate_count"] == 0
    assert before_knowledge["missed_count"] == 0
    assert not any(
        row.get("week_ending") == "2025-01-03"
        for row in before_knowledge["pending_events"]
    )

    observed_stale = sleeve.build_tsa_checkpoint_throughput_paper_sleeve_snapshot(
        as_of_date="2025-01-13",
        records=records,
        ohlcv_by_ticker=bars,
        state=before_knowledge["state"],
    )
    assert observed_stale["candidate_count"] == 0
    assert observed_stale["open_position_count"] == 0
    assert observed_stale["closed_event_count"] == 0
    assert observed_stale["missed_count"] == 1
    assert observed_stale["new_missed_count"] == 1
    missed = observed_stale["missed_events"][0]
    assert missed["status"] == "missed_fail_closed_late_discovery"
    assert missed["intended_entry_date"] == "2025-01-07"
    # No session strictly after the 2025-01-13 knowledge date is observable in
    # the as-of snapshot, but the knowledge date is already after intended entry.
    assert missed["first_available_entry_date"] is None
    assert missed["entry_date"] is None
    assert observed_stale["orders"] == []


def test_source_failure_returns_zero_gate3_events_and_no_partial_trades() -> None:
    records = _records()
    records[-1].pop("source_url")
    replay = sleeve.replay_tsa_checkpoint_throughput_paper_trades(
        records=records,
        ohlcv_by_ticker=_bars(),
        start="2025-01-01",
        end="2025-01-31",
    )
    assert replay["candidate_audit"]["measurement_valid"] is False
    assert replay["signals_generated"] == 0
    assert replay["signals_survived"] == 0
    assert replay["survival_rate"] == 0.0
    assert replay["selected_candidates"] == []
    assert replay["trades"] == []
    assert replay["event_trades"] == []
    assert replay["orders"] == []


def test_empty_snapshot_is_explicitly_default_off() -> None:
    empty = sleeve.empty_tsa_checkpoint_throughput_paper_sleeve_snapshot(
        "2025-01-07", "fixture_failure"
    )
    assert empty["status"] == "unavailable"
    assert empty["reason"] == "fixture_failure"
    assert empty["candidate_count"] == 0
    assert empty["pending_events"] == []
    assert empty["open_events"] == []
    assert empty["closed_events"] == []
    assert empty["missed_events"] == []
    assert empty["orders"] == []
    assert empty["trade_enabled"] is False
    assert empty["production_impact"]["alters_orders"] is False
