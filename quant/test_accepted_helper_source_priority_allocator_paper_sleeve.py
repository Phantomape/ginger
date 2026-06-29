from __future__ import annotations

from datetime import date, timedelta

from quant.accepted_helper_source_priority_allocator_paper_sleeve import (
    OUTCOME_CONTRACT_RULE_VERSION,
    RULE_VERSION,
    SOURCE_PRIORITY,
    SOURCE_RULE_VERSION,
    TARGET_PRICE_STATUS,
    build_accepted_helper_source_priority_allocator_snapshot,
    empty_accepted_helper_source_priority_allocator_state,
    select_accepted_helper_source_priority_rows,
)


def _business_dates(days: int) -> list[str]:
    current = date(2026, 1, 5)
    out: list[str] = []
    while len(out) < days:
        if current.weekday() < 5:
            out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def _ohlcv(days: int = 20) -> dict[str, list[dict]]:
    dates = _business_dates(days)
    payload: dict[str, list[dict]] = {}
    for ticker, base in {"SPY": 100.0, "TOP": 80.0, "ALT": 75.0}.items():
        rows = []
        close = base
        for idx, day in enumerate(dates):
            open_ = close
            close = open_ * (1.0 + 0.001 + idx * 0.0001)
            rows.append(
                {
                    "date": day,
                    "open": round(open_, 4),
                    "high": round(close * 1.01, 4),
                    "low": round(open_ * 0.99, 4),
                    "close": round(close, 4),
                    "volume": 1_000_000,
                }
            )
        payload[ticker] = rows
    return payload


def test_selects_fixed_source_priority_top1_per_day() -> None:
    trading_dates = _business_dates(5)
    signal_date = trading_dates[1]

    selected, rejected, audit = select_accepted_helper_source_priority_rows(
        source_rows=[
            {
                "ticker": "ALT",
                "date": signal_date,
                "source_family": "rolling_peer_shock",
                "candidate_score": 999.0,
            },
            {
                "ticker": "TOP",
                "date": signal_date,
                "source_family": "volatility_relief",
                "candidate_score": 1.0,
            },
        ],
        trading_dates=trading_dates,
        create_trades=False,
    )

    assert [row["ticker"] for row in selected] == ["TOP"]
    assert selected[0]["source_family"] == "volatility_relief"
    assert selected[0]["rule_version"] == RULE_VERSION
    assert selected[0]["source_rule_version"] == SOURCE_RULE_VERSION
    assert selected[0]["trade_enabled"] is False
    assert rejected[0]["filter_reason"] == "daily_top1_source_priority_limit"
    assert audit["selected_source_counts"] == {"volatility_relief": 1}


def test_same_ticker_cooldown_blocks_nearby_repeat() -> None:
    trading_dates = _business_dates(15)

    selected, rejected, audit = select_accepted_helper_source_priority_rows(
        source_rows=[
            {
                "ticker": "TOP",
                "date": trading_dates[1],
                "source_family": "volatility_relief",
                "candidate_score": 1.0,
            },
            {
                "ticker": "TOP",
                "date": trading_dates[8],
                "source_family": "volatility_relief",
                "candidate_score": 2.0,
            },
        ],
        trading_dates=trading_dates,
        create_trades=False,
    )

    assert [row["signal_date"] for row in selected] == [trading_dates[1]]
    assert rejected[0]["filter_reason"] == "same_ticker_cooldown"
    assert audit["filtered_priority_candidate_count"] == 1


def test_lagged_consensus_source_ranked_first() -> None:
    trading_dates = _business_dates(5)
    signal_date = trading_dates[1]

    selected, rejected, audit = select_accepted_helper_source_priority_rows(
        source_rows=[
            {
                "ticker": "ALT",
                "date": signal_date,
                "source_family": "volatility_relief",
                "candidate_score": 999.0,
            },
            {
                "ticker": "TOP",
                "date": signal_date,
                "source_family": "lagged_cross_source_consensus",
                "source_family_count": 2,
                "source_count": 3,
                "has_lagged_independent_confirmation": True,
            },
        ],
        trading_dates=trading_dates,
        create_trades=False,
    )

    assert SOURCE_PRIORITY["lagged_cross_source_consensus"]["rank"] == 1
    assert SOURCE_PRIORITY["volatility_relief"]["rank"] == 2
    assert [row["ticker"] for row in selected] == ["TOP"]
    assert selected[0]["source_family"] == "lagged_cross_source_consensus"
    assert selected[0]["source_notional_scalar"] == 1.25
    assert selected[0]["paper_notional_usd"] == 5000.0
    assert selected[0]["uses_free_ohlcv_only"] is False
    assert selected[0]["uses_free_non_ohlcv"] is True
    assert rejected[0]["source_family"] == "volatility_relief"
    assert rejected[0]["filter_reason"] == "daily_top1_source_priority_limit"
    assert audit["selected_source_counts"] == {"lagged_cross_source_consensus": 1}
    assert audit["source_notional_scalars"]["lagged_cross_source_consensus"] == 1.25


def test_revision_source_ranked_ahead_of_compression() -> None:
    trading_dates = _business_dates(5)
    signal_date = trading_dates[1]

    selected, rejected, audit = select_accepted_helper_source_priority_rows(
        source_rows=[
            {
                "ticker": "ALT",
                "date": signal_date,
                "source_family": "compression",
                "candidate_score": 999.0,
            },
            {
                "ticker": "TOP",
                "date": signal_date,
                "source_family": "revision_surprise_low_extension",
                "candidate_score": 1.0,
            },
        ],
        trading_dates=trading_dates,
        create_trades=False,
    )

    assert SOURCE_PRIORITY["revision_surprise_low_extension"]["rank"] == 6
    assert SOURCE_PRIORITY["compression"]["rank"] == 7
    assert [row["ticker"] for row in selected] == ["TOP"]
    assert selected[0]["source_family"] == "revision_surprise_low_extension"
    assert selected[0]["source_priority_rank"] == 6
    assert selected[0]["uses_free_ohlcv_only"] is False
    assert selected[0]["uses_free_non_ohlcv"] is True
    assert rejected[0]["source_family"] == "compression"
    assert rejected[0]["filter_reason"] == "daily_top1_source_priority_limit"
    assert audit["selected_source_counts"] == {"revision_surprise_low_extension": 1}


def test_independent_source_notional_scalar_keeps_selection_order() -> None:
    trading_dates = _business_dates(5)
    signal_date = trading_dates[1]

    selected, rejected, audit = select_accepted_helper_source_priority_rows(
        source_rows=[
            {
                "ticker": "TOP",
                "date": signal_date,
                "source_family": "industry_laggard_repair",
                "candidate_score": 1.0,
            }
        ],
        trading_dates=trading_dates,
        create_trades=False,
    )

    assert not rejected
    assert [row["ticker"] for row in selected] == ["TOP"]
    assert selected[0]["source_priority_rank"] == SOURCE_PRIORITY["industry_laggard_repair"][
        "rank"
    ]
    assert selected[0]["base_paper_notional_usd"] == 4000.0
    assert selected[0]["source_notional_scalar"] == 1.25
    assert selected[0]["paper_notional_usd"] == 5000.0
    assert audit["source_notional_scalars"]["industry_laggard_repair"] == 1.25


def test_daily_snapshot_creates_default_off_pending_from_source_snapshots() -> None:
    ohlcv = _ohlcv()
    signal_date = ohlcv["SPY"][5]["date"]

    snapshot = build_accepted_helper_source_priority_allocator_snapshot(
        as_of=signal_date,
        source_snapshots={
            "rolling_peer_shock": {
                "candidate_count": 1,
                "candidates": [
                    {
                        "ticker": "ALT",
                        "date": signal_date,
                        "source_family": "rolling_peer_shock",
                        "candidate_score": 999.0,
                    }
                ],
            },
            "volatility_relief": {
                "candidate_count": 1,
                "candidates": [
                    {
                        "ticker": "TOP",
                        "date": signal_date,
                        "source_family": "volatility_relief",
                        "candidate_score": 1.0,
                    }
                ],
            },
        },
        ohlcv_by_ticker=ohlcv,
        state=empty_accepted_helper_source_priority_allocator_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["pending_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["alters_orders"] is False
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "TOP"
    assert candidate["source_family"] == "volatility_relief"
    assert candidate["outcome_contract_rule_version"] == OUTCOME_CONTRACT_RULE_VERSION
    assert candidate["exit_rule"] == "time_exit_after_10_trading_days"
    assert candidate["target_price"] is None
    assert candidate["target_price_required"] is False
    assert candidate["target_price_status"] == TARGET_PRICE_STATUS
    pending = snapshot["new_pending_entries"][0]
    assert pending["entry_date_status"] == "pending_next_session_open"
    assert pending["target_price_status"] == TARGET_PRICE_STATUS
    assert pending["trade_enabled"] is False
    assert pending["alters_orders"] is False
    assert snapshot["source_priority_context"]["priority_audit"][
        "selected_source_counts"
    ] == {"volatility_relief": 1}


def test_daily_snapshot_uses_lagged_consensus_snapshot_as_rank_one_source() -> None:
    ohlcv = _ohlcv()
    signal_date = ohlcv["SPY"][5]["date"]

    snapshot = build_accepted_helper_source_priority_allocator_snapshot(
        as_of=signal_date,
        source_snapshots={
            "lagged_cross_source_consensus": {
                "candidate_count": 1,
                "candidates": [
                    {
                        "ticker": "TOP",
                        "date": signal_date,
                        "source_family_count": 2,
                        "source_count": 3,
                        "has_lagged_independent_confirmation": True,
                    }
                ],
            },
            "volatility_relief": {
                "candidate_count": 1,
                "candidates": [
                    {
                        "ticker": "ALT",
                        "date": signal_date,
                        "source_family": "volatility_relief",
                        "candidate_score": 999.0,
                    }
                ],
            },
        },
        ohlcv_by_ticker=ohlcv,
        state=empty_accepted_helper_source_priority_allocator_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["trade_enabled"] is False
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "TOP"
    assert candidate["source_family"] == "lagged_cross_source_consensus"
    assert candidate["source_priority_rank"] == 1
    assert candidate["source_notional_scalar"] == 1.25
    assert candidate["paper_notional_usd"] == 5000.0
    assert snapshot["new_pending_entries"][0]["paper_notional_usd"] == 5000.0
    assert snapshot["source_priority_context"]["priority_audit"][
        "selected_source_counts"
    ] == {"lagged_cross_source_consensus": 1}


def test_daily_snapshot_preserves_independent_source_scaled_pending_notional() -> None:
    ohlcv = _ohlcv()
    signal_date = ohlcv["SPY"][5]["date"]

    snapshot = build_accepted_helper_source_priority_allocator_snapshot(
        as_of=signal_date,
        source_snapshots={
            "industry_laggard_repair": {
                "candidate_count": 1,
                "candidates": [
                    {
                        "ticker": "TOP",
                        "date": signal_date,
                        "source_family": "industry_laggard_repair",
                        "candidate_score": 1.0,
                    }
                ],
            }
        },
        ohlcv_by_ticker=ohlcv,
        state=empty_accepted_helper_source_priority_allocator_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    candidate = snapshot["candidates"][0]
    pending = snapshot["new_pending_entries"][0]
    assert candidate["source_family"] == "industry_laggard_repair"
    assert candidate["source_notional_scalar"] == 1.25
    assert candidate["paper_notional_usd"] == 5000.0
    assert pending["paper_notional_usd"] == 5000.0
    assert pending["trade_enabled"] is False


def test_daily_snapshot_preserves_peer_shock_scaled_pending_notional() -> None:
    ohlcv = _ohlcv()
    signal_date = ohlcv["SPY"][5]["date"]

    snapshot = build_accepted_helper_source_priority_allocator_snapshot(
        as_of=signal_date,
        source_snapshots={
            "rolling_peer_shock": {
                "candidate_count": 1,
                "candidates": [
                    {
                        "ticker": "TOP",
                        "date": signal_date,
                        "source_family": "rolling_peer_shock",
                        "candidate_score": 1.0,
                    }
                ],
            }
        },
        ohlcv_by_ticker=ohlcv,
        state=empty_accepted_helper_source_priority_allocator_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    candidate = snapshot["candidates"][0]
    pending = snapshot["new_pending_entries"][0]
    assert candidate["source_family"] == "rolling_peer_shock"
    assert candidate["source_notional_scalar"] == 1.25
    assert candidate["paper_notional_usd"] == 5000.0
    assert pending["paper_notional_usd"] == 5000.0
    assert pending["trade_enabled"] is False


def test_daily_snapshot_preserves_turn_of_month_scaled_pending_notional() -> None:
    ohlcv = _ohlcv()
    signal_date = ohlcv["SPY"][5]["date"]

    snapshot = build_accepted_helper_source_priority_allocator_snapshot(
        as_of=signal_date,
        source_snapshots={
            "turn_of_month": {
                "candidate_count": 1,
                "candidates": [
                    {
                        "ticker": "TOP",
                        "date": signal_date,
                        "source_family": "turn_of_month",
                        "candidate_score": 1.0,
                    }
                ],
            }
        },
        ohlcv_by_ticker=ohlcv,
        state=empty_accepted_helper_source_priority_allocator_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    candidate = snapshot["candidates"][0]
    pending = snapshot["new_pending_entries"][0]
    assert candidate["source_family"] == "turn_of_month"
    assert candidate["source_notional_scalar"] == 1.25
    assert candidate["paper_notional_usd"] == 5000.0
    assert pending["paper_notional_usd"] == 5000.0
    assert pending["trade_enabled"] is False


def test_daily_snapshot_marks_open_allocator_position_with_last_price() -> None:
    ohlcv = _ohlcv()
    state = empty_accepted_helper_source_priority_allocator_state()
    entry_date = ohlcv["TOP"][5]["date"]
    as_of = ohlcv["TOP"][7]["date"]
    state["open_positions"] = [
        {
            "decision_id": f"{RULE_VERSION}:synthetic-open-price",
            "ticker": "TOP",
            "signal_date": ohlcv["TOP"][4]["date"],
            "entry_date": entry_date,
            "entry_price": 100.0,
            "notional_usd": 5000.0,
            "paper_notional_usd": 5000.0,
            "hold_days": 10,
            "observed_trading_days": 2,
            "last_observed_date": ohlcv["TOP"][6]["date"],
            "paper_status": "open",
            "trade_enabled": False,
        }
    ]

    snapshot = build_accepted_helper_source_priority_allocator_snapshot(
        as_of=as_of,
        source_snapshots={},
        ohlcv_by_ticker=ohlcv,
        state=state,
        config={"hold_days": 10},
        persist=False,
    )

    assert snapshot["open_position_count"] == 1
    assert snapshot["closed_count_today"] == 0
    position = snapshot["open_positions"][0]
    expected_last = ohlcv["TOP"][7]["close"]
    assert position["last_price"] == expected_last
    assert position["last_price_asof"] == as_of
    assert position["observed_trading_days"] == 3
    assert position["paper_status"] == "open"
    assert position["outcome_contract_rule_version"] == OUTCOME_CONTRACT_RULE_VERSION
    assert position["exit_rule"] == "time_exit_after_10_trading_days"
    assert position["entry_date_status"] == "present"
    assert position["target_price"] is None
    assert position["target_price_required"] is False
    assert position["target_price_status"] == TARGET_PRICE_STATUS
    assert position["trade_enabled"] is False
    assert position["unrealized_return_pct"] == round((expected_last / 100.0) - 1.0, 6)
    assert position["unrealized_pnl"] == round(5000.0 * ((expected_last / 100.0) - 1.0), 2)
