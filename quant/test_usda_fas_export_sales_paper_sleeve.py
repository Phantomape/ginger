from __future__ import annotations

import copy
from datetime import date, timedelta

import pytest

from quant import usda_fas_export_sales_paper_sleeve as sleeve


def _weekly_records(
    *,
    sales_from_end: dict[int, tuple[float, float]] | None = None,
) -> list[dict]:
    sales_from_end = sales_from_end or {}
    week = date(2016, 1, 7)
    final_week = date(2025, 6, 5)
    weeks: list[date] = []
    while week <= final_week:
        weeks.append(week)
        week += timedelta(days=7)
    output: list[dict] = []
    for idx, week_ending in enumerate(weeks):
        offset = len(weeks) - 1 - idx
        corn, soybeans = sales_from_end.get(offset, (1_000.0, 1_000.0))
        release_date = week_ending + timedelta(days=7)
        output.append(
            {
                "release_date": release_date.isoformat(),
                "week_ending": week_ending.isoformat(),
                "corn_net_sales_mt": corn,
                "soybeans_net_sales_mt": soybeans,
                "source_url": (
                    "https://apps.fas.usda.gov/export-sales/archive/"
                    f"{release_date:%Y%m%d}.pdf"
                ),
                "raw_sha256": f"{idx + 1:064x}",
            }
        )
    return output


def _triggering_records() -> list[dict]:
    return _weekly_records(sales_from_end={0: (2_000.0, 2_000.0)})


def _weekdays(start: str, count: int) -> list[str]:
    current = date.fromisoformat(start)
    output: list[str] = []
    while len(output) < count:
        if current.weekday() < 5:
            output.append(current.isoformat())
        current += timedelta(days=1)
    return output


def _bars(
    *,
    volume_overrides: dict[str, float] | None = None,
    low_price_tickers: set[str] | None = None,
) -> dict[str, list[dict]]:
    volume_overrides = volume_overrides or {}
    low_price_tickers = low_price_tickers or set()
    days = _weekdays("2025-04-01", 90)
    output: dict[str, list[dict]] = {}
    for ticker in sleeve.AGRICULTURE_BASKET_V1:
        price = 9.0 if ticker in low_price_tickers else 100.0
        default_volume = 10_000.0 if ticker in sleeve.ETF_TICKERS else 1_000_000.0
        volume = volume_overrides.get(ticker, default_volume)
        output[ticker] = [
            {
                "date": day,
                "open": price,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price,
                "volume": volume,
            }
            for day in days
        ]
    return output


def _future_record(*, malformed_hash: bool = False) -> dict:
    release_date = date(2025, 6, 19)
    return {
        "release_date": release_date.isoformat(),
        "week_ending": "2025-06-12",
        "corn_net_sales_mt": 99_000.0,
        "soybeans_net_sales_mt": -99_000.0,
        "source_url": (
            "https://apps.fas.usda.gov/export-sales/archive/"
            f"{release_date:%Y%m%d}.pdf"
        ),
        "raw_sha256": "malformed" if malformed_hash else "f" * 64,
    }


def test_policy_constants_are_frozen_and_default_off() -> None:
    assert sleeve.AGRICULTURE_BASKET_V1 == (
        "CORN", "SOYB", "DBA", "ADM", "BG", "CTVA", "DE", "MOS", "NTR", "CF"
    )
    assert sleeve.ETF_TICKERS == {"CORN", "SOYB", "DBA"}
    assert sleeve.LEG_NOTIONAL_USD == 500.0
    assert sleeve.COOLDOWN_SESSIONS == 10
    assert sleeve.HOLD_SESSIONS == 10
    assert sleeve.ROUND_TRIP_COST_PCT == pytest.approx(0.0035)
    assert sleeve._production_impact()["trade_enabled"] is False


def test_pit_seasonal_midrank_prior104_nearest_rank_p75_and_strict_gt() -> None:
    evaluations, audit = sleeve.evaluate_usda_fas_export_sales_events(
        _triggering_records()
    )
    final = evaluations[-1]
    assert audit["measurement_valid"] is True
    assert final["event_ready"] is True
    assert all(
        count >= sleeve.MIN_SEASONAL_OBSERVATIONS
        for count in final["seasonal_observation_counts"].values()
    )
    assert final["seasonal_percentiles"] == {"corn": 1.0, "soybeans": 1.0}
    assert final["export_sales_composite"] == 1.0
    assert final["trailing_composite_count"] == 104
    assert final["prior_104_composite_p75"] == 0.5
    assert final["triggered"] is True

    equal_evaluations, _ = sleeve.evaluate_usda_fas_export_sales_events(
        _weekly_records()
    )
    equal_final = equal_evaluations[-1]
    assert equal_final["seasonal_percentiles"] == {"corn": 0.5, "soybeans": 0.5}
    assert equal_final["export_sales_composite"] == 0.5
    assert equal_final["prior_104_composite_p75"] == 0.5
    assert equal_final["threshold_passed"] is False
    assert equal_final["triggered"] is False

    assert sleeve._nearest_rank([1, 2, 3, 4], 0.75) == 3


def test_future_records_do_not_change_prior_release_decision() -> None:
    records = _triggering_records()
    before, _ = sleeve.evaluate_usda_fas_export_sales_events(records)
    after, _ = sleeve.evaluate_usda_fas_export_sales_events(
        [*records, _future_record()]
    )
    before_row = next(row for row in before if row["release_date"] == "2025-06-12")
    after_row = next(row for row in after if row["release_date"] == "2025-06-12")
    keys = (
        "seasonal_percentiles",
        "export_sales_composite",
        "trailing_composite_count",
        "prior_104_composite_p75",
        "triggered",
        "filter_reason",
    )
    assert {key: before_row[key] for key in keys} == {
        key: after_row[key] for key in keys
    }


def test_simultaneous_release_rows_share_strictly_prior_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two 08:30 catch-up PDFs cannot become history for one another."""

    def fake_seasonal_percentile(
        history: list[dict],
        *,
        current_week_ending: str,
        field: str,
        current_value: float,
    ) -> tuple[float, int]:
        del history, current_week_ending, field
        return float(current_value), 15

    monkeypatch.setattr(sleeve, "_seasonal_percentile", fake_seasonal_percentile)

    def record(
        week_ending: date,
        release_date: date,
        composite: float,
        identity: int,
    ) -> dict:
        return {
            "release_date": release_date.isoformat(),
            "week_ending": week_ending.isoformat(),
            "corn_net_sales_mt": composite,
            "soybeans_net_sales_mt": composite,
            "source_url": (
                "https://apps.fas.usda.gov/export-sales/archive/"
                f"simultaneous-{identity}.pdf"
            ),
            "raw_sha256": f"{identity:064x}",
        }

    first_catchup_week = date(2022, 9, 1)
    prior_weeks = [
        first_catchup_week - timedelta(days=7 * offset)
        for offset in range(104, 0, -1)
    ]
    # The correct prior-104 p75 is 1.0: 77 zeros followed by 27 ones.
    # If the first simultaneous composite (0.0) leaks into the second row,
    # the oldest 1.0 drops out and the second row's p75 incorrectly becomes 0.
    prior_composites = [1.0, *([0.0] * 77), *([1.0] * 26)]
    prior = [
        record(week, week + timedelta(days=7), composite, idx + 1)
        for idx, (week, composite) in enumerate(
            zip(prior_weeks, prior_composites, strict=True)
        )
    ]
    release = date(2022, 9, 15)
    first = record(first_catchup_week, release, 0.0, 201)
    second = record(date(2022, 9, 8), release, 0.5, 202)
    future = record(date(2022, 9, 15), date(2022, 9, 22), 0.25, 203)

    normal, normal_audit = sleeve.evaluate_usda_fas_export_sales_events(
        [*prior, first, second, future]
    )
    swapped, swapped_audit = sleeve.evaluate_usda_fas_export_sales_events(
        [*prior, second, first, future]
    )
    assert normal_audit["valid_composite_count"] == 107
    assert swapped_audit["valid_composite_count"] == 107

    keys = (
        "prior_release_record_count",
        "prior_valid_composite_total_count",
        "simultaneous_release_group_size",
        "trailing_composite_count",
        "prior_104_composite_p75",
        "triggered",
    )
    normal_by_week = {row["week_ending"]: row for row in normal}
    swapped_by_week = {row["week_ending"]: row for row in swapped}
    for week in ("2022-09-01", "2022-09-08"):
        row = normal_by_week[week]
        assert {key: row[key] for key in keys} == {
            key: swapped_by_week[week][key] for key in keys
        }
        assert row["prior_release_record_count"] == 104
        assert row["prior_valid_composite_total_count"] == 104
        assert row["simultaneous_release_group_size"] == 2
        assert row["prior_104_composite_p75"] == 1.0
        assert row["triggered"] is False

    # A strictly later release sees both simultaneous composites at once.
    future_row = normal_by_week["2022-09-15"]
    assert future_row["prior_release_record_count"] == 106
    assert future_row["prior_valid_composite_total_count"] == 106
    assert future_row["simultaneous_release_group_size"] == 1
    assert future_row["prior_104_composite_p75"] == 0.5


def test_malformed_provenance_is_a_measurement_hard_fail() -> None:
    records = _triggering_records()
    records[-1]["source_url"] = "https://example.com/export-sales.pdf"
    candidates, audit = sleeve.build_usda_fas_export_sales_agriculture_basket_candidates(
        records=records,
        ohlcv_by_ticker=_bars(),
        start="2025-06-01",
        end="2025-07-31",
    )
    assert candidates == []
    assert audit["measurement_valid"] is False
    assert audit["source_contract_error_count"] > 0
    assert audit["signals_survived"] == 0

    bad_hash = _triggering_records()
    bad_hash[-1]["raw_sha256"] = "not-a-sha256"
    assert sleeve.normalise_usda_fas_export_sales_records(bad_hash) == []


def test_official_0830_release_enters_same_day_with_all_ten_legs() -> None:
    candidates, audit = sleeve.build_usda_fas_export_sales_agriculture_basket_candidates(
        records=_triggering_records(),
        ohlcv_by_ticker=_bars(),
        start="2025-06-01",
        end="2025-07-31",
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["release_date"] == "2025-06-12"
    assert candidate["entry_date"] == candidate["release_date"]
    assert candidate["eligible_tickers"] == list(sleeve.AGRICULTURE_BASKET_V1)
    assert candidate["eligible_leg_count"] == 10
    assert candidate["all_ten_legs_eligible"] is True
    assert candidate["event_notional_usd"] == 5_000.0
    assert {leg["paper_notional_usd"] for leg in candidate["legs"]} == {500.0}
    assert all(leg["entry_date"] and leg["target_price"] for leg in candidate["legs"])
    assert candidate["provenance"]["raw_sha256"] == _triggering_records()[-1]["raw_sha256"]
    assert candidate["policy_audit"]["same_day_regular_open_allowed"] is True
    assert audit["signals_survived"] == 1
    assert audit["selected_leg_count"] == 10


def test_liquidity_is_ticker_type_specific_and_any_missing_leg_rejects_event() -> None:
    at_etf_boundary, _ = sleeve.build_usda_fas_export_sales_agriculture_basket_candidates(
        records=_triggering_records(),
        ohlcv_by_ticker=_bars(volume_overrides={"CORN": 2_500.0}),
        start="2025-06-01",
        end="2025-07-31",
    )
    assert len(at_etf_boundary) == 1
    corn = next(leg for leg in at_etf_boundary[0]["legs"] if leg["ticker"] == "CORN")
    assert corn["avg_dollar_volume_20d"] == 250_000.0
    assert corn["notional_adv_fraction"] == pytest.approx(0.002)

    low_etf, low_etf_audit = (
        sleeve.build_usda_fas_export_sales_agriculture_basket_candidates(
            records=_triggering_records(),
            ohlcv_by_ticker=_bars(volume_overrides={"CORN": 2_499.0}),
            start="2025-06-01",
            end="2025-07-31",
        )
    )
    assert low_etf == []
    assert low_etf_audit["reject_totals"]["not_all_10_legs_eligible"] == 1
    assert low_etf_audit["reject_totals"]["leg_etf_adv20_below_250k"] == 1

    low_equity, low_equity_audit = (
        sleeve.build_usda_fas_export_sales_agriculture_basket_candidates(
            records=_triggering_records(),
            ohlcv_by_ticker=_bars(volume_overrides={"CF": 499_999.0}),
            start="2025-06-01",
            end="2025-07-31",
        )
    )
    assert low_equity == []
    assert low_equity_audit["reject_totals"]["leg_equity_adv20_below_50m"] == 1

    low_price, low_price_audit = (
        sleeve.build_usda_fas_export_sales_agriculture_basket_candidates(
            records=_triggering_records(),
            ohlcv_by_ticker=_bars(low_price_tickers={"CF"}),
            start="2025-06-01",
            end="2025-07-31",
        )
    )
    assert low_price == []
    assert low_price_audit["reject_totals"]["leg_entry_price_below_10"] == 1


def test_ten_session_cooldown_is_on_event_decisions_not_legs() -> None:
    records = _weekly_records(
        sales_from_end={1: (2_000.0, 2_000.0), 0: (2_000.0, 2_000.0)}
    )
    candidates, audit = sleeve.build_usda_fas_export_sales_agriculture_basket_candidates(
        records=records,
        ohlcv_by_ticker=_bars(),
        start="2025-05-25",
        end="2025-07-31",
    )
    assert len(candidates) == 1
    assert candidates[0]["release_date"] == "2025-06-05"
    assert audit["reject_totals"]["ten_session_cooldown"] == 1


def test_replay_uses_target_then_tenth_session_close_and_35bps_cost() -> None:
    bars = _bars()
    entry_date = "2025-06-12"
    corn_entry = next(row for row in bars["CORN"] if row["date"] == entry_date)
    corn_entry["high"] = 200.0
    replay = sleeve.replay_usda_fas_export_sales_agriculture_basket_paper_trades(
        records=_triggering_records(),
        ohlcv_by_ticker=bars,
        start="2025-06-01",
        end="2025-07-31",
    )
    assert replay["signals_survived"] == 1
    assert len(replay["trades"]) == 10
    assert len(replay["event_trades"]) == 1
    corn = next(row for row in replay["trades"] if row["ticker"] == "CORN")
    adm = next(row for row in replay["trades"] if row["ticker"] == "ADM")
    assert corn["exit_date"] == entry_date
    assert corn["exit_reason"] == "atr_3_5x_target"
    assert corn["hold_sessions_realized"] == 1
    assert adm["exit_reason"] == "scheduled_10th_session_close"
    assert adm["hold_sessions_realized"] == 10
    expected_return = adm["exit_price"] / adm["entry_price"] - 1.0 - 0.0035
    assert adm["pnl_pct_net"] == pytest.approx(expected_return, abs=1e-10)
    assert adm["pnl"] == pytest.approx(500.0 * expected_return, abs=0.01)
    assert all(row["trade_enabled"] is False for row in replay["trades"])
    assert replay["trade_enabled"] is False
    assert replay["orders"] == []


def test_daily_snapshot_is_asof_safe_deduped_and_trade_disabled() -> None:
    records = [*_triggering_records(), _future_record(malformed_hash=True)]
    bars = _bars()
    snapshot = sleeve.build_usda_fas_export_sales_agriculture_basket_paper_snapshot(
        as_of_date="2025-06-12",
        records=records,
        ohlcv_by_ticker=bars,
    )
    assert snapshot["audit"]["measurement_valid"] is True
    assert snapshot["audit"]["future_record_count_ignored"] == 1
    assert snapshot["source_trigger_count"] == 1
    assert snapshot["candidate_count"] == 1
    assert snapshot["pending_count"] == 0
    assert snapshot["candidates"][0]["entry_date"] == "2025-06-12"
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["trade_enabled"] is False
    assert snapshot["orders"] == []

    duplicate = sleeve.build_usda_fas_export_sales_agriculture_basket_paper_snapshot(
        as_of_date="2025-06-12",
        records=records,
        ohlcv_by_ticker=bars,
        state=snapshot["state"],
    )
    assert duplicate["candidate_count"] == 0
    assert duplicate["state"] == snapshot["state"]


def test_duplicate_week_fails_closed() -> None:
    records = _triggering_records()
    duplicate = copy.deepcopy(records[-1])
    duplicate["release_date"] = "2025-06-13"
    duplicate["source_url"] = (
        "https://apps.fas.usda.gov/export-sales/archive/20250613.pdf"
    )
    duplicate["raw_sha256"] = "a" * 64
    assert sleeve.normalise_usda_fas_export_sales_records([*records, duplicate]) == []


def test_shutdown_catchup_release_lag_accepts_through_70_days_only() -> None:
    catchup = {
        "release_date": "2025-12-01",
        "week_ending": "2025-10-02",  # 60-day shutdown catch-up lag.
        "corn_net_sales_mt": 1_000.0,
        "soybeans_net_sales_mt": 1_000.0,
        "source_url": "https://apps.fas.usda.gov/export-sales/archive/catchup.pdf",
        "raw_sha256": "b" * 64,
    }
    normalised = sleeve.normalise_usda_fas_export_sales_records([catchup])
    assert len(normalised) == 1
    assert normalised[0]["release_lag_days"] == 60

    too_late = copy.deepcopy(catchup)
    too_late["week_ending"] = "2025-09-21"  # 71 days.
    assert sleeve.normalise_usda_fas_export_sales_records([too_late]) == []

    second_week_same_release = copy.deepcopy(catchup)
    second_week_same_release["week_ending"] = "2025-10-09"
    second_week_same_release["raw_sha256"] = "c" * 64
    same_day_catchup = sleeve.normalise_usda_fas_export_sales_records(
        [catchup, second_week_same_release]
    )
    assert [row["release_lag_days"] for row in same_day_catchup] == [60, 53]
