from __future__ import annotations

from datetime import date, timedelta

import pytest

import sec_cash_tender_spread_paper_sleeve as sleeve


def _bars(
    *,
    start: str = "2024-11-01",
    end: str = "2025-04-01",
    announcement: str = "2025-01-02",
    break_close: float = 8.0,
    post_close: float = 9.55,
    entry_open: float = 9.5,
    volume: float = 1_000_000.0,
) -> list[dict]:
    rows: list[dict] = []
    current = date.fromisoformat(start)
    finish = date.fromisoformat(end)
    while current <= finish:
        if sleeve.is_us_equity_session(current):
            day = current.isoformat()
            close = break_close if day < announcement else post_close
            # The announcement close must never leak into the strict-prior
            # break value.
            if day == announcement:
                close = 100.0
            open_price = entry_open if day == "2025-01-13" else close
            rows.append(
                {
                    "date": day,
                    "open": open_price,
                    "high": max(open_price, close) + 1.0,
                    "low": min(open_price, close) - 1.0,
                    "close": close,
                    "volume": volume,
                }
            )
        current += timedelta(days=1)
    return rows


def _set_bar(rows: list[dict], day: str, **changes: float) -> None:
    row = next(item for item in rows if item["date"] == day)
    row.update(changes)
    row["high"] = max(float(row["open"]), float(row["close"])) + 1.0
    row["low"] = max(
        0.001, min(float(row["open"]), float(row["close"])) - 1.0
    )


def _episode(
    accession: str = "0000000001-25-000001",
    ticker: str = "TEND",
    *,
    outcome_status: str = "pending",
    outcome_date: str | None = None,
    cash_price: float | None = None,
    offer_price: float = 10.0,
    expiration_date: str = "2025-03-31",
    amendments: list[dict] | None = None,
) -> dict:
    return {
        "accession_number": accession,
        "subject_cik": accession[:10],
        "filing_date": "2025-01-10",  # Friday
        "accepted_at": "2025-01-10T18:20:00",
        "policy_eligible": True,
        "raw_submission_url": f"https://www.sec.gov/Archives/{accession}.txt",
        "raw_submission_sha256": "a" * 64,
        "primary_schedule_to": {
            "source_url": f"https://www.sec.gov/Archives/{accession}/primary.htm",
            "source_sha256": "b" * 64,
        },
        "offer_to_purchase_exhibit": {
            "source_url": f"https://www.sec.gov/Archives/{accession}/offer.htm",
            "source_sha256": "c" * 64,
        },
        "terms": {
            "target_ticker": ticker,
            "target_exchange": "NASDAQ",
            "agreement_or_announcement_date": "2025-01-02",
            "offer_price_usd": offer_price,
            "scheduled_expiration_date": expiration_date,
            "evidence_spans": [{"field": "offer_price_usd", "source_sha256": "c" * 64}],
        },
        "outcome": {
            "outcome_type": outcome_status,
            "outcome_date": outcome_date,
            "cash_price_usd": cash_price,
            "evidence_spans": [{"field": "outcome", "source_sha256": "b" * 64}],
        },
        "amendments": [] if amendments is None else amendments,
    }


def _replay(
    episode: dict,
    rows: list[dict] | None = None,
    *,
    end: str = "2025-01-17",
    fee: float = 20.0,
) -> dict:
    return sleeve.replay_sec_cash_tender_spread_sleeve(
        [episode],
        {episode["accession_number"]: rows or _bars()},
        "2025-01-10",
        end,
        event_fee_usd=fee,
    )


def test_strict_next_session_entry_and_strict_prior_20_close_break_value() -> None:
    result = _replay(_episode())
    candidate = result["candidate_evaluations"][0]
    entered = next(row for row in result["events"] if row["event"] == "entered")

    assert candidate["entry_date"] == "2025-01-13"
    assert entered["entry_date"] == "2025-01-13"
    assert entered["entry_price"] == pytest.approx(9.5)
    assert candidate["break_lookback_session_count"] == 20
    assert candidate["break_value"] == pytest.approx(8.0)
    assert candidate["break_value_method"].startswith("arithmetic_mean_of_strictly_prior")
    assert candidate["implied_completion_probability"] >= 0.70


def test_one_off_nyse_closure_is_not_treated_as_an_entry_session() -> None:
    episode = _episode()
    episode["filing_date"] = "2025-01-08"
    episode["accepted_at"] = "2025-01-08T18:20:00"
    result = sleeve.replay_sec_cash_tender_spread_sleeve(
        [episode],
        {episode["accession_number"]: _bars()},
        "2025-01-08",
        "2025-01-17",
    )

    assert result["candidate_evaluations"][0]["entry_date"] == "2025-01-10"
    assert "2025-01-09" not in [row["date"] for row in result["daily_ledger"]]


def test_implied_probability_below_seventy_percent_rejects() -> None:
    rows = _bars(entry_open=8.8)
    result = _replay(_episode(), rows)

    assert result["trades"] == []
    assert result["signals_survived"] == 0
    assert (
        "implied_completion_probability_below_70pct"
        in result["candidate_rejections"][0]["rejection_reasons"]
    )


def test_completion_uses_actual_cash_on_second_post_public_session_and_charges_carry_fee() -> None:
    episode = _episode(
        outcome_status="completed",
        outcome_date="2025-01-17",  # Friday before MLK Day
        cash_price=10.2,
    )
    result = _replay(episode, end="2025-01-23")
    trade = result["trades"][0]

    assert trade["exit_date"] == "2025-01-22"  # Jan 21 first, Jan 22 second
    assert trade["exit_reason"] == "completed_cash_settlement"
    assert trade["exit_price"] == pytest.approx(10.2)
    assert trade["actual_cash_payout"] is True
    assert trade["actual_close"] is True
    assert trade["right_censored"] is False
    assert trade["carry_days"] == 9
    assert trade["accrued_carry"] == pytest.approx(
        trade["entry_notional"] * 0.05 * 9 / 365.0
    )
    assert trade["event_fee_usd"] == 20.0
    assert trade["target_price_role"] == "contract_cash_offer_price"
    assert trade["sec_provenance"]["source_hashes"] == ["a" * 64, "b" * 64, "c" * 64]
    assert trade["sec_provenance"]["terms_evidence_refs"]
    assert trade["sec_provenance"]["outcome_evidence_refs"]
    assert result["metrics"]["cash_conservation_passed"] is True
    entry_mark = next(row for row in result["daily_ledger"] if row["date"] == "2025-01-13")
    next_mark = next(row for row in result["daily_ledger"] if row["date"] == "2025-01-14")
    assert entry_mark["accrued_carry"] == pytest.approx(
        trade["entry_notional"] * 0.05 / 365.0
    )
    assert next_mark["accrued_carry"] == pytest.approx(
        trade["entry_notional"] * 0.05 * 2 / 365.0
    )


def test_flat_fee_sensitivity_changes_after_cost_pnl_by_exact_fee() -> None:
    episode = _episode(
        outcome_status="completed",
        outcome_date="2025-01-17",
        cash_price=10.0,
        offer_price=9.75,
        expiration_date="2025-02-12",
    )
    rows = _bars(
        break_close=9.4,
        post_close=9.65,
        entry_open=9.63,
    )
    fee_zero = _replay(episode, rows, end="2025-01-23", fee=0)
    fee_twenty = _replay(episode, rows, end="2025-01-23", fee=20)

    assert fee_zero["trades"][0]["shares"] == fee_twenty["trades"][0]["shares"]
    assert (
        fee_zero["trades"][0]["net_pnl_usd"]
        - fee_twenty["trades"][0]["net_pnl_usd"]
        == pytest.approx(20.0)
    )
    assert set(fee_twenty["event_fee_sensitivity"]) == {"0", "20", "40"}
    assert fee_twenty["event_fee_sensitivity"]["40"]["trade_count"] == 0
    assert fee_twenty["event_fee_sensitivity"]["20"]["binding_policy_fee"] is True
    assert fee_twenty["event_fee_sensitivity"]["20"]["measurement_valid"] is True
    assert fee_twenty["event_fee_sensitivity"]["20"]["measurement_failure_count"] == 0


@pytest.mark.parametrize(
    ("status", "expected_reason"),
    [
        ("terminated_negative", "terminated_negative"),
        ("terminated_higher_bid", "terminated_higher_bid"),
    ],
)
def test_termination_exits_at_next_session_open(status: str, expected_reason: str) -> None:
    rows = _bars()
    _set_bar(rows, "2025-01-16", open=7.75, close=7.9)
    episode = _episode(outcome_status=status, outcome_date="2025-01-15")
    trade = _replay(episode, rows)["trades"][0]

    assert trade["exit_date"] == "2025-01-16"
    assert trade["exit_price"] == pytest.approx(7.75)
    assert trade["exit_reason"] == expected_reason


def test_public_higher_bid_exits_at_next_session_open() -> None:
    rows = _bars()
    _set_bar(rows, "2025-01-16", open=10.6, close=10.7)
    episode = _episode(outcome_status="higher_bid_pending", outcome_date="2025-01-15")
    trade = _replay(episode, rows)["trades"][0]

    assert trade["exit_date"] == "2025-01-16"
    assert trade["exit_price"] == pytest.approx(10.6)
    assert trade["exit_reason"] == "higher_bid_pending_public_exit"


def test_earliest_public_terminal_amendment_controls_exit_chronology() -> None:
    rows = _bars()
    _set_bar(rows, "2025-01-16", open=7.6, close=7.7)
    episode = _episode(
        outcome_status="completed",
        outcome_date="2025-01-17",
        cash_price=10.2,
        amendments=[
            {
                "accession_number": "0000000001-25-000002",
                "filing_date": "2025-01-15",
                "outcome": {"outcome_type": "terminated_negative"},
            },
            {
                "accession_number": "0000000001-25-000003",
                "filing_date": "2025-01-17",
                "outcome": {"outcome_type": "completed"},
            },
        ],
    )
    trade = _replay(episode, rows, end="2025-01-23")["trades"][0]

    assert trade["exit_date"] == "2025-01-16"
    assert trade["exit_reason"] == "terminated_negative"
    assert trade["exit_price"] == pytest.approx(7.6)


def test_earlier_completion_cannot_use_a_later_future_revised_cash_price() -> None:
    episode = _episode(
        outcome_status="completed",
        outcome_date="2025-01-20",
        cash_price=12.0,
        amendments=[
            {
                "accession_number": "0000000001-25-000002",
                "filing_date": "2025-01-15",
                "accepted_at": "2025-01-15T17:00:00",
                "outcome": {"outcome_type": "completed"},
            },
            {
                "accession_number": "0000000001-25-000003",
                "filing_date": "2025-01-20",
                "accepted_at": "2025-01-20T17:00:00",
                "outcome": {
                    "outcome_type": "higher_bid_pending",
                    "higher_bid_price_usd": 12.0,
                },
            },
        ],
    )
    episode["outcome"]["higher_bid_prices"] = [
        {
            "filing_date": "2025-01-20",
            "accession_number": "0000000001-25-000003",
            "price_usd": 12.0,
        }
    ]
    trade = _replay(episode, end="2025-01-23")["trades"][0]

    assert trade["exit_date"] == "2025-01-17"
    assert trade["exit_reason"] == "completed_cash_settlement"
    assert trade["exit_price"] == pytest.approx(10.0)


def test_completion_ignores_unaccepted_competing_price_as_cash_payout() -> None:
    episode = _episode(
        outcome_status="completed",
        outcome_date="2025-01-17",
        cash_price=12.0,
    )
    episode["outcome"]["higher_bid_prices"] = [
        {
            "filing_date": "2025-01-15",
            "accession_number": "0000000001-25-000002",
            "price_usd": 12.0,
            # No accepted/revised-offer evidence: this is only a proposal.
        }
    ]
    trade = _replay(episode, end="2025-01-23")["trades"][0]

    assert trade["exit_reason"] == "completed_cash_settlement"
    assert trade["exit_price"] == pytest.approx(10.0)
    assert trade["actual_cash_payout"] is True


def test_same_entry_day_after_open_amendment_does_not_cancel_prior_open_entry() -> None:
    rows = _bars()
    _set_bar(rows, "2025-01-14", open=7.5, close=7.6)
    episode = _episode(
        amendments=[
            {
                "accession_number": "0000000001-25-000002",
                "filing_date": "2025-01-13",
                "accepted_at": "2025-01-13T16:05:00",
                "outcome": {"outcome_type": "terminated_negative"},
            }
        ]
    )
    trade = _replay(episode, rows)["trades"][0]

    assert trade["entry_date"] == "2025-01-13"
    assert trade["exit_date"] == "2025-01-14"
    assert trade["exit_reason"] == "terminated_negative"


def test_same_entry_day_premarket_amendment_fails_entry_closed() -> None:
    episode = _episode(
        amendments=[
            {
                "accession_number": "0000000001-25-000002",
                "filing_date": "2025-01-13",
                "accepted_at": "2025-01-13T08:45:00",
                "outcome": {"outcome_type": "terminated_negative"},
            }
        ]
    )
    result = _replay(episode)

    assert result["signals_survived"] == 0
    assert "decisive_amendment_public_before_entry" in (
        result["candidate_rejections"][0]["rejection_reasons"]
    )


def test_later_premarket_termination_exits_at_same_session_open() -> None:
    rows = _bars()
    _set_bar(rows, "2025-01-15", open=8.4, close=8.3)
    episode = _episode(
        amendments=[
            {
                "accession_number": "0000000001-25-000002",
                "filing_date": "2025-01-15",
                "accepted_at": "2025-01-15T08:10:00",
                "outcome": {"outcome_type": "terminated_higher_bid"},
            }
        ]
    )
    trade = _replay(episode, rows)["trades"][0]

    assert trade["entry_date"] == "2025-01-13"
    assert trade["exit_date"] == "2025-01-15"
    assert trade["exit_price"] == pytest.approx(8.4)
    assert trade["exit_reason"] == "terminated_higher_bid"


def test_policy_invalidating_amendment_exits_at_next_session_open() -> None:
    rows = _bars()
    _set_bar(rows, "2025-01-16", open=8.25, close=8.3)
    episode = _episode(
        amendments=[
            {
                "accession_number": "0000000001-25-000002",
                "filing_date": "2025-01-15",
                "policy_eligible": False,
            }
        ]
    )
    trade = _replay(episode, rows)["trades"][0]

    assert trade["exit_date"] == "2025-01-16"
    assert trade["exit_price"] == pytest.approx(8.25)
    assert trade["exit_reason"] == "policy_invalidating_amendment"


def test_pending_deal_times_out_after_365_calendar_days_at_session_open() -> None:
    rows = _bars(end="2026-01-20", post_close=9.8, entry_open=9.8)
    episode = _episode(offer_price=11.0, expiration_date="2026-02-27")
    trade = _replay(episode, rows, end="2026-01-16")["trades"][0]

    assert trade["entry_date"] == "2025-01-13"
    assert trade["exit_date"] == "2026-01-13"
    assert trade["exit_reason"] == "365_calendar_day_timeout"
    assert trade["carry_days"] == 365


def test_window_end_is_right_censored_mtm_not_an_actual_close() -> None:
    result = _replay(_episode(), end="2025-01-17")
    trade = result["trades"][0]

    assert trade["right_censored"] is True
    assert trade["actual_close"] is False
    assert trade["exit_date"] is None
    assert trade["exit_price"] is None
    assert trade["valuation_date"] == "2025-01-17"
    assert trade["valuation_price"] == pytest.approx(9.55)
    assert result["actual_closed_trades"] == []
    assert result["open_positions"]
    assert result["entered_trade_count"] == 1
    assert result["actual_closed_trade_count"] == 0
    assert result["metrics"]["trade_count"] == 0
    assert result["metrics"]["entered_trade_count"] == 1
    assert result["metrics"]["win_rate"] is None
    assert result["metrics"]["concentration"]["row_count"] == 0
    assert result["metrics"]["mtm_inclusive_concentration"]["row_count"] == 1


def test_stale_window_end_mark_is_disclosed_as_measurement_failure() -> None:
    rows = [row for row in _bars() if row["date"] != "2025-01-17"]
    result = _replay(_episode(), rows, end="2025-01-17")
    trade = result["trades"][0]

    assert trade["right_censored"] is True
    assert trade["mark_is_exact_window_close"] is False
    assert trade["valuation_price_date"] == "2025-01-16"
    assert any(
        row["reason"] == "missing_exact_window_end_close_stale_mtm_disclosed"
        for row in result["measurement_failures"]
    )
    assert result["binding_metrics"] is None
    assert result["binding_measurement_status"] == "fail_closed"


def test_funded_cash_conservation_concurrency_and_no_leverage() -> None:
    episodes: list[dict] = []
    prices: dict[str, list[dict]] = {}
    for index, ticker in enumerate(("AAA", "BBB", "CCC"), start=1):
        accession = f"000000000{index}-25-000001"
        episode = _episode(
            accession,
            ticker,
            offer_price=9.75,
            expiration_date="2025-02-12",
        )
        episodes.append(episode)
        prices[accession] = _bars(
            break_close=9.4,
            post_close=9.65,
            entry_open=9.63,
        )

    result = sleeve.replay_sec_cash_tender_spread_sleeve(
        episodes, prices, "2025-01-10", "2025-01-17"
    )
    entered = [row for row in result["events"] if row["event"] == "entered"]

    assert len(entered) == 2
    assert result["metrics"]["maximum_open_count"] == 2
    assert result["metrics"]["maximum_concurrent_notional"] <= 10_000.0
    assert all(row["entry_notional"] <= 5_000.0 for row in entered)
    assert all(row["predicted_break_loss"] <= 500.0 for row in entered)
    assert all(
        position["adv_fraction"] <= 0.01 for position in result["open_positions"]
    )
    assert result["metrics"]["minimum_cash"] >= 0.0
    assert result["metrics"]["cash_nonnegative"] is True
    assert result["metrics"]["cash_conservation_passed"] is True
    assert result["metrics"]["cash_transition_reconciliation_passed"] is True
    assert any(
        "insufficient_unreused_sleeve_cash" in row["rejection_reasons"]
        or "concurrent_notional_cap_exhausted" in row["rejection_reasons"]
        for row in result["candidate_rejections"]
    )
    assert result["execution_sizing_contract"]["same_session_exit_proceeds_reused"] is False
    assert all(
        {
            "cash",
            "market_value",
            "accrued_carry",
            "equity",
            "daily_return",
            "open_count",
        }
        <= row.keys()
        for row in result["daily_ledger"]
    )
    assert [row["date"] for row in result["daily_ledger"]] == [
        "2025-01-10",
        "2025-01-13",
        "2025-01-14",
        "2025-01-15",
        "2025-01-16",
        "2025-01-17",
    ]


def test_liability_reserves_prevent_negative_cash_on_two_near_zero_breaks() -> None:
    episodes: list[dict] = []
    prices: dict[str, list[dict]] = {}
    for index, ticker in enumerate(("AAA", "BBB"), start=1):
        accession = f"000000001{index}-25-000001"
        episode = _episode(
            accession,
            ticker,
            outcome_status="terminated_negative",
            outcome_date="2025-01-15",
            offer_price=9.75,
            expiration_date="2025-02-12",
        )
        rows = _bars(
            break_close=9.4,
            post_close=9.65,
            entry_open=9.63,
        )
        _set_bar(rows, "2025-01-16", open=0.01, close=0.01)
        episodes.append(episode)
        prices[accession] = rows

    result = sleeve.replay_sec_cash_tender_spread_sleeve(
        episodes, prices, "2025-01-10", "2025-01-17"
    )

    assert len(result["trades"]) == 2
    assert all(trade["actual_close"] for trade in result["trades"])
    assert result["metrics"]["cash_nonnegative"] is True
    assert result["metrics"]["minimum_cash"] >= 0.0
    assert result["metrics"]["cash_transition_reconciliation_passed"] is True


def test_negative_return_and_negative_sharpe_produce_negative_ev() -> None:
    ledger = [
        {
            "as_of": "2025-01-02",
            "cash": 9_900.0,
            "market_value": 0.0,
            "accrued_carry": 0.0,
            "accrued_exit_cost": 0.0,
            "accrued_event_fees": 0.0,
            "equity": 9_900.0,
            "daily_return": -0.01,
            "open_count": 0,
        },
        {
            "as_of": "2025-01-03",
            "cash": 9_750.0,
            "market_value": 0.0,
            "accrued_carry": 0.0,
            "accrued_exit_cost": 0.0,
            "accrued_event_fees": 0.0,
            "equity": 9_750.0,
            "daily_return": 9_750.0 / 9_900.0 - 1.0,
            "open_count": 0,
        },
    ]
    metrics = sleeve.compute_sec_cash_tender_spread_metrics(ledger, [])

    assert metrics["strategy_total_return_pct"] < 0
    assert metrics["sharpe_daily"] < 0
    assert metrics["expected_value_score"] < 0


def test_daily_snapshot_reuses_policy_and_is_irrevocably_default_off() -> None:
    episode = _episode(
        outcome_status="completed",
        outcome_date="2025-01-17",
        cash_price=10.2,
    )
    snapshot = sleeve.build_sec_cash_tender_spread_paper_snapshot(
        "2025-01-13",
        [episode],
        {episode["accession_number"]: _bars()},
        start="2025-01-10",
    )

    assert snapshot["rule_version"] == sleeve.RULE_VERSION
    assert snapshot["trade_enabled"] is False
    assert snapshot["enabled"] is False
    assert snapshot["orders"] == []
    assert snapshot["llm"] == {"used": False, "authority": "none"}
    assert snapshot["production_impact"]["uses_llm"] is False
    assert snapshot["production_impact"]["alters_orders"] is False
    assert snapshot["events"][0]["entry_date"] == "2025-01-13"
    assert snapshot["latest_ledger"]["open_count"] == 1
    # Full historical input was supplied, but the daily surface must not expose
    # or act on the future completion amendment.
    assert snapshot["open_positions"][0]["outcome_status"] == "pending"
    assert snapshot["open_positions"][0]["exit_action"]["kind"] == "365_calendar_day_timeout"


def test_filing_day_snapshot_is_pending_and_does_not_read_future_entry_open() -> None:
    episode = _episode()
    rows = _bars(entry_open=123.45)
    snapshot = sleeve.build_sec_cash_tender_spread_paper_snapshot(
        "2025-01-10",
        [episode],
        {episode["accession_number"]: rows},
        start="2025-01-10",
    )

    candidate = snapshot["candidate_evaluations"][0]
    assert candidate["status"] == "pending_next_session_open"
    assert candidate["entry_date"] == "2025-01-13"
    assert candidate["entry_price"] is None
    assert snapshot["events"] == []
    assert snapshot["latest_ledger"]["cash"] == 10_000.0


def test_daily_snapshot_preserves_visible_malformed_ohlcv_as_fail_closed() -> None:
    episode = _episode()
    rows = _bars()
    del next(row for row in rows if row["date"] == "2025-01-10")["volume"]
    snapshot = sleeve.build_sec_cash_tender_spread_paper_snapshot(
        "2025-01-13",
        [episode],
        {episode["accession_number"]: rows},
        start="2025-01-10",
    )

    assert snapshot["trades"] == []
    assert snapshot["candidate_rejections"]
    assert "invalid_ohlcv_rows" in snapshot["candidate_rejections"][0][
        "rejection_reasons"
    ]


def test_replay_ignores_malformed_price_rows_after_window_end() -> None:
    episode = _episode()
    rows = _bars()
    future = next(row for row in rows if row["date"] == "2025-03-03")
    del future["volume"]
    result = _replay(episode, rows, end="2025-01-17")

    assert result["signals_survived"] == 1
    assert result["candidate_rejections"] == []


def test_missing_required_event_open_is_terminal_and_snapshot_fails_closed() -> None:
    episode = _episode(
        outcome_status="terminated_negative", outcome_date="2025-01-15"
    )
    rows = [row for row in _bars() if row["date"] != "2025-01-16"]
    result = _replay(episode, rows, end="2025-01-17")
    trade = result["trades"][0]

    assert trade["right_censored"] is True
    assert trade["censor_reason"] == "missing_exact_required_event_exit_open"
    assert result["open_positions"][0]["terminally_blocked"] is True
    assert result["metrics"]["measurement_valid"] is False
    assert any(
        row["reason"] == "missing_exact_required_event_exit_open"
        for row in result["measurement_failures"]
    )

    snapshot = sleeve.build_sec_cash_tender_spread_paper_snapshot(
        "2025-01-17",
        [episode],
        {episode["accession_number"]: rows},
        start="2025-01-10",
    )
    assert snapshot["status"] == "fail_closed"
    assert snapshot["reason"] == "measurement_failure"


def test_missing_required_episode_fields_fail_closed_with_all_reasons() -> None:
    episode = _episode()
    del episode["accepted_at"]
    del episode["terms"]["target_exchange"]
    episode["outcome"] = {}
    result = _replay(episode)
    reasons = result["candidate_rejections"][0]["rejection_reasons"]

    assert result["signals_survived"] == 0
    assert result["trades"] == []
    assert "missing_exchange" in reasons
    assert "missing_accepted_at" in reasons
    assert "missing_outcome" in reasons
