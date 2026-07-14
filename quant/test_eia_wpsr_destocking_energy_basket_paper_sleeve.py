from __future__ import annotations

import copy
from datetime import date, timedelta

import pytest

from quant import eia_wpsr_destocking_energy_basket_paper_sleeve as sleeve


def _weekly_records(
    *,
    draws_from_end: dict[int, tuple[float, float, float]] | None = None,
) -> list[dict]:
    draws = draws_from_end or {}
    week = date(2017, 1, 6)
    final_week = date(2025, 6, 6)
    weeks: list[date] = []
    while week <= final_week:
        weeks.append(week)
        week += timedelta(days=7)
    output: list[dict] = []
    for idx, week_ending in enumerate(weeks):
        offset = len(weeks) - 1 - idx
        differences = draws.get(offset, (0.0, 0.0, 0.0))
        release_date = week_ending + timedelta(days=5)
        inventories = {}
        for series, difference in zip(sleeve.INVENTORY_SERIES, differences, strict=True):
            prior = 1_000.0
            inventories[series] = {
                "current": prior + difference,
                "prior": prior,
                "difference": difference,
                "implied_corrected_prior": prior,
                "arithmetic_residual": 0.0,
            }
        output.append(
            {
                "release_date": release_date.isoformat(),
                "week_ending": week_ending.isoformat(),
                "inventories": inventories,
                "difference_semantics": "published_difference",
                "source_url": (
                    "https://www.eia.gov/petroleum/supply/weekly/archive/"
                    f"{release_date:%Y}/{release_date:%Y_%m_%d}/csv/table4.csv"
                ),
                "raw_sha256": f"{idx:064x}",
            }
        )
    return output


def _weekdays(start: str, count: int) -> list[str]:
    current = date.fromisoformat(start)
    output: list[str] = []
    while len(output) < count:
        if current.weekday() < 5:
            output.append(current.isoformat())
        current += timedelta(days=1)
    return output


def _bars(*, low_price_tickers: set[str] | None = None) -> dict[str, list[dict]]:
    low_price_tickers = low_price_tickers or set()
    days = _weekdays("2025-04-01", 90)
    output: dict[str, list[dict]] = {}
    for ticker in sleeve.ENERGY_BASKET_V1:
        price = 9.0 if ticker in low_price_tickers else 100.0
        output[ticker] = [
            {
                "date": day,
                "open": price,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price,
                "volume": 1_000_000.0,
            }
            for day in days
        ]
    return output


def _triggering_records() -> list[dict]:
    # Two of the three frozen series are broad draws.  The third is flat.
    return _weekly_records(draws_from_end={0: (-100.0, -100.0, 0.0)})


def test_policy_constants_are_frozen_and_default_off() -> None:
    assert sleeve.INVENTORY_SERIES == (
        "commercial_crude_oil_excluding_spr",
        "total_motor_gasoline",
        "distillate_fuel_oil",
    )
    assert sleeve.ENERGY_BASKET_V1 == (
        "XOM", "CVX", "COP", "EOG", "OXY", "SLB", "BKR", "MPC", "VLO", "PSX"
    )
    assert sleeve.LEG_NOTIONAL_USD == 1_000.0
    assert sleeve.COOLDOWN_SESSIONS == 10
    assert sleeve.HOLD_SESSIONS == 10
    assert sleeve.ROUND_TRIP_COST_PCT == pytest.approx(0.0035)
    assert sleeve._production_impact()["trade_enabled"] is False


def test_pit_seasonal_composite_uses_prior_history_nearest_rank_and_strict_gt() -> None:
    evaluations, audit = sleeve.evaluate_eia_wpsr_destocking_events(_triggering_records())
    final = evaluations[-1]
    assert audit["measurement_valid"] is True
    assert final["event_ready"] is True
    assert all(count >= 15 for count in final["seasonal_observation_counts"].values())
    assert final["trailing_score_count"] == 104
    assert final["trailing_score_p80"] == 0.0
    assert final["negative_excess_series_count"] == 2
    assert final["destocking_score"] > final["trailing_score_p80"]
    assert final["triggered"] is True

    equal_evaluations, _ = sleeve.evaluate_eia_wpsr_destocking_events(_weekly_records())
    equal_final = equal_evaluations[-1]
    assert equal_final["destocking_score"] == equal_final["trailing_score_p80"] == 0.0
    assert equal_final["threshold_passed"] is False
    assert equal_final["triggered"] is False

    one_draw, _ = sleeve.evaluate_eia_wpsr_destocking_events(
        _weekly_records(draws_from_end={0: (-100.0, 0.0, 0.0)})
    )
    assert one_draw[-1]["destocking_score"] > 0
    assert one_draw[-1]["negative_excess_series_count"] == 1
    assert one_draw[-1]["triggered"] is False


def test_nearest_rank_p80_is_not_interpolated() -> None:
    assert sleeve._nearest_rank([1, 2, 3, 4, 100], 0.80) == 4


def test_candidate_is_one_event_with_fixed_legs_next_open_and_gate3_denominator() -> None:
    records = _triggering_records()
    candidates, audit = sleeve.build_eia_wpsr_destocking_energy_basket_candidates(
        records=records,
        ohlcv_by_ticker=_bars(),
        start="2025-06-01",
        end="2025-07-31",
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["release_date"] == "2025-06-11"
    assert candidate["entry_date"] == "2025-06-12"
    assert candidate["entry_date"] > candidate["release_date"]
    assert candidate["eligible_tickers"] == list(sleeve.ENERGY_BASKET_V1)
    assert candidate["eligible_leg_count"] == 10
    assert candidate["event_notional_usd"] == 10_000.0
    assert all(leg["entry_date"] and leg["target_price"] for leg in candidate["legs"])
    # Weekly releases are the opportunities; ten equity legs are not ten signals.
    assert audit["signals_generated"] > 1
    assert audit["signals_survived"] == 1
    assert audit["selected_leg_count"] == 10
    assert audit["survival_rate"] == pytest.approx(1 / audit["signals_generated"], abs=1e-6)


def test_at_least_eight_liquid_legs_and_no_notional_redistribution() -> None:
    records = _triggering_records()
    two_missing = {"XOM", "CVX"}
    candidates, _ = sleeve.build_eia_wpsr_destocking_energy_basket_candidates(
        records=records,
        ohlcv_by_ticker=_bars(low_price_tickers=two_missing),
        start="2025-06-01",
        end="2025-07-31",
    )
    assert len(candidates) == 1
    assert candidates[0]["eligible_leg_count"] == 8
    assert candidates[0]["event_notional_usd"] == 8_000.0
    assert {leg["paper_notional_usd"] for leg in candidates[0]["legs"]} == {1_000.0}

    rejected, audit = sleeve.build_eia_wpsr_destocking_energy_basket_candidates(
        records=records,
        ohlcv_by_ticker=_bars(low_price_tickers={"XOM", "CVX", "COP"}),
        start="2025-06-01",
        end="2025-07-31",
    )
    assert rejected == []
    assert audit["signals_survived"] == 0
    assert audit["reject_totals"]["fewer_than_8_eligible_legs"] == 1


def test_ten_session_cooldown_is_applied_to_event_decisions_not_legs() -> None:
    records = _weekly_records(
        draws_from_end={
            1: (-100.0, -100.0, 0.0),
            0: (-100.0, -100.0, 0.0),
        }
    )
    candidates, audit = sleeve.build_eia_wpsr_destocking_energy_basket_candidates(
        records=records,
        ohlcv_by_ticker=_bars(),
        start="2025-05-25",
        end="2025-07-31",
    )
    assert len(candidates) == 1
    assert candidates[0]["release_date"] == "2025-06-04"
    assert audit["reject_totals"]["ten_session_cooldown"] == 1


def test_replay_uses_slipped_next_open_target_then_tenth_session_close_and_cost() -> None:
    records = _triggering_records()
    bars = _bars()
    entry_date = "2025-06-12"
    xom_entry = next(row for row in bars["XOM"] if row["date"] == entry_date)
    xom_entry["high"] = 200.0  # force the locked target on the entry session
    replay = sleeve.replay_eia_wpsr_destocking_energy_basket_paper_trades(
        records=records,
        ohlcv_by_ticker=bars,
        start="2025-06-01",
        end="2025-07-31",
    )
    assert replay["signals_survived"] == 1
    assert len(replay["trades"]) == 10
    assert len(replay["event_trades"]) == 1
    xom = next(row for row in replay["trades"] if row["ticker"] == "XOM")
    cvx = next(row for row in replay["trades"] if row["ticker"] == "CVX")
    assert xom["entry_date"] == entry_date
    assert xom["exit_date"] == entry_date
    assert xom["exit_reason"] == "atr_3_5x_target"
    assert xom["hold_sessions_realized"] == 1
    assert xom["target_price"] > xom["entry_price"]
    assert cvx["exit_reason"] == "scheduled_10th_session_close"
    assert cvx["hold_sessions_realized"] == 10
    expected_return = cvx["exit_price"] / cvx["entry_price"] - 1.0 - 0.0035
    assert cvx["pnl_pct_net"] == pytest.approx(expected_return, abs=1e-10)
    assert cvx["pnl"] == pytest.approx(1_000.0 * expected_return, abs=0.01)
    assert all(row["trade_enabled"] is False for row in replay["trades"])
    assert replay["orders"] == []


def test_daily_snapshot_is_asof_safe_deduped_and_matches_replay_on_entry_day() -> None:
    records = _triggering_records()
    bars = _bars()
    replay = sleeve.replay_eia_wpsr_destocking_energy_basket_paper_trades(
        records=records,
        ohlcv_by_ticker=bars,
        start="2025-06-01",
        end="2025-07-31",
    )
    release_snapshot = sleeve.build_eia_wpsr_destocking_energy_basket_paper_sleeve_snapshot(
        as_of_date="2025-06-11",
        records=records,
        ohlcv_by_ticker=bars,
    )
    assert release_snapshot["candidate_count"] == 0
    assert release_snapshot["pending_count"] == 1
    assert release_snapshot["source_trigger_count"] == 1
    assert release_snapshot["pending_entries"][0]["release_date"] == "2025-06-11"
    assert "entry_date" not in release_snapshot["pending_entries"][0]

    entry_snapshot = sleeve.build_eia_wpsr_destocking_energy_basket_paper_sleeve_snapshot(
        as_of_date="2025-06-12",
        records=records,
        ohlcv_by_ticker=bars,
        state=release_snapshot["state"],
    )
    assert entry_snapshot["candidate_count"] == 1
    assert entry_snapshot["pending_count"] == 0
    assert entry_snapshot["candidates"][0]["decision_id"] == replay["selected_candidates"][0]["decision_id"]
    assert entry_snapshot["candidates"][0]["entry_date"] == "2025-06-12"

    duplicate_snapshot = sleeve.build_eia_wpsr_destocking_energy_basket_paper_sleeve_snapshot(
        as_of_date="2025-06-12",
        records=records,
        ohlcv_by_ticker=bars,
        state=entry_snapshot["state"],
    )
    assert duplicate_snapshot["candidate_count"] == 0
    assert duplicate_snapshot["state"] == entry_snapshot["state"]
    assert entry_snapshot["trade_enabled"] is False
    assert entry_snapshot["production_impact"]["trade_enabled"] is False
    assert entry_snapshot["orders"] == []


def test_malformed_table4_record_is_a_measurement_hard_fail() -> None:
    records = _triggering_records()
    records[-1]["inventories"][sleeve.INVENTORY_SERIES[0]]["difference"] = -99.0
    candidates, audit = sleeve.build_eia_wpsr_destocking_energy_basket_candidates(
        records=records,
        ohlcv_by_ticker=_bars(),
        start="2025-06-01",
        end="2025-07-31",
    )
    assert candidates == []
    assert audit["measurement_valid"] is False
    assert audit["source_contract_error_count"] > 0
    assert audit["signals_survived"] == 0


def test_source_contract_requires_official_archive_hash_lag_and_unique_week() -> None:
    valid = _weekly_records()[-2:]
    assert len(sleeve.normalise_eia_wpsr_table4_records(valid)) == 2

    bad_url = copy.deepcopy(valid)
    bad_url[-1]["source_url"] = "https://example.com/table4.csv"
    assert sleeve.normalise_eia_wpsr_table4_records(bad_url) == []

    bad_hash = copy.deepcopy(valid)
    bad_hash[-1]["raw_sha256"] = "not-a-sha256"
    assert sleeve.normalise_eia_wpsr_table4_records(bad_hash) == []

    duplicate_week = copy.deepcopy(valid)
    duplicate_week[-1]["week_ending"] = duplicate_week[-2]["week_ending"]
    assert sleeve.normalise_eia_wpsr_table4_records(duplicate_week) == []

    bad_lag = copy.deepcopy(valid)
    bad_lag[-1]["week_ending"] = (
        date.fromisoformat(bad_lag[-1]["release_date"]) - timedelta(days=14)
    ).isoformat()
    assert sleeve.normalise_eia_wpsr_table4_records(bad_lag) == []


def test_official_errata_uses_published_difference_and_implied_corrected_prior() -> None:
    record = copy.deepcopy(_weekly_records()[0])
    record.update(
        {
            "release_date": "2023-12-28",
            "week_ending": "2023-12-22",
            "source_url": (
                "https://www.eia.gov/petroleum/supply/weekly/archive/"
                "2023/2023_12_28/csv/table4.csv"
            ),
            "difference_semantics": "official_errata_revision",
            "official_notice_url": "https://www.eia.gov/petroleum/supply/weekly/notice.php",
            "official_notice_sha256": "a" * 64,
        }
    )
    for row in record["inventories"].values():
        row.update(
            {
                "current": 900.0,
                "prior": 950.0,
                "difference": -100.0,
                "implied_corrected_prior": 1_000.0,
                "arithmetic_residual": -50.0,
            }
        )

    normalised = sleeve.normalise_eia_wpsr_table4_records([record])
    assert len(normalised) == 1
    for row in normalised[0]["inventories"].values():
        assert row["prior"] == 950.0
        assert row["implied_corrected_prior"] == 1_000.0
        assert row["arithmetic_residual"] == -50.0
        assert row["weekly_change_rate"] == pytest.approx(-0.1)

    missing_notice = copy.deepcopy(record)
    missing_notice.pop("official_notice_sha256")
    assert sleeve.normalise_eia_wpsr_table4_records([missing_notice]) == []

    wrong_release = copy.deepcopy(record)
    wrong_release["release_date"] = "2023-12-27"
    wrong_release["source_url"] = wrong_release["source_url"].replace(
        "2023_12_28", "2023_12_27"
    )
    assert sleeve.normalise_eia_wpsr_table4_records([wrong_release]) == []


def test_non_errata_displayed_prior_must_match_implied_corrected_prior() -> None:
    record = copy.deepcopy(_weekly_records()[0])
    first = sleeve.INVENTORY_SERIES[0]
    record["inventories"][first]["prior"] += 1.0
    assert sleeve.normalise_eia_wpsr_table4_records([record]) == []


def test_iso_week_radius_respects_52_and_53_week_year_boundaries() -> None:
    assert date(2021, 12, 28).isocalendar().week == 52
    assert date(2020, 12, 28).isocalendar().week == 53
    assert sleeve._iso_week_distance(1, 51, 2021) == 2
    assert sleeve._iso_week_distance(1, 52, 2021) == 1
    assert sleeve._iso_week_distance(1, 53, 2020) == 1
    assert sleeve._iso_week_distance(53, 52, 2021) == 0


def test_missing_shared_session_bar_makes_whole_event_unsettled() -> None:
    bars = _bars()
    bars["XOM"] = [row for row in bars["XOM"] if row["date"] != "2025-06-17"]
    replay = sleeve.replay_eia_wpsr_destocking_energy_basket_paper_trades(
        records=_triggering_records(),
        ohlcv_by_ticker=bars,
        start="2025-06-01",
        end="2025-07-31",
    )

    assert replay["signals_survived"] == 1
    assert replay["trades"] == []
    assert replay["event_trades"] == []
    assert len(replay["unsettled"]) == 1
    assert replay["unsettled"][0]["unsettled_reason"] == (
        "incomplete_shared_session_ohlc"
    )
    assert replay["unsettled"][0]["incomplete_bars"] == [
        {"ticker": "XOM", "date": "2025-06-17", "missing_fields": ["open", "high", "low", "close"]}
    ]


def test_daily_snapshot_ignores_future_malformed_source_rows() -> None:
    records = _triggering_records()
    future = copy.deepcopy(records[-1])
    future.update(
        {
            "release_date": "2025-06-18",
            "week_ending": "2025-06-13",
            "source_url": future["source_url"].replace("2025_06_11", "2025_06_18"),
            "raw_sha256": "malformed-future-hash",
        }
    )
    snapshot = sleeve.build_eia_wpsr_destocking_energy_basket_paper_sleeve_snapshot(
        as_of_date="2025-06-11",
        records=[*records, future],
        ohlcv_by_ticker=_bars(),
    )

    assert snapshot["audit"]["measurement_valid"] is True
    assert snapshot["source_trigger_count"] == 1
    assert snapshot["candidate_count"] == 0
    assert snapshot["pending_count"] == 1
