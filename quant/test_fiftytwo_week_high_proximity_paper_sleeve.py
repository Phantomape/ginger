from __future__ import annotations

from datetime import date, timedelta

from quant.fiftytwo_week_high_proximity_paper_sleeve import (
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_fiftytwo_week_high_proximity_historical_trades,
    build_fiftytwo_week_high_proximity_snapshot,
    empty_fiftytwo_week_high_proximity_state,
    evaluate_fiftytwo_week_high_kill_switch,
)

SIGNAL_DAY = 260
TOTAL_DAYS = 275


def _business_dates(days: int) -> list[str]:
    current = date(2025, 1, 1)
    out: list[str] = []
    while len(out) < days:
        if current.weekday() < 5:
            out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def _rows(
    *,
    base: float,
    returns: list[float],
    signal_day: int,
    volume: float = 1_500_000.0,
) -> list[dict]:
    rows = []
    close = base
    for idx, day in enumerate(_business_dates(len(returns))):
        ret = returns[idx]
        open_ = close
        close = close * (1.0 + ret)
        low = min(open_, close) * 0.994
        high = max(open_, close) * 1.002
        rows.append(
            {
                "date": day,
                "open": round(open_, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": volume * (1.25 if idx == signal_day else 1.0),
            }
        )
    return rows


def _returns(kind: str, days: int = TOTAL_DAYS, signal_day: int = SIGNAL_DAY) -> list[float]:
    if kind == "spy":
        return [0.001 for _ in range(days)]
    if kind == "leader":
        # steady uptrend keeps the stock at its 52-week high; the signal-day
        # push creates a fresh 60-day-high breakout with high close location.
        values = [0.002 for _ in range(days)]
        values[signal_day] = 0.010
        return values
    if kind == "faded":
        # an early run-up then a long fade leaves the close far below the
        # trailing 252-day high, so proximity fails.
        values = [0.004 if idx < 120 else -0.001 for idx in range(days)]
        values[signal_day] = 0.010
        return values
    raise AssertionError(kind)


def _ohlcv() -> dict[str, list[dict]]:
    return {
        "SPY": _rows(base=100.0, returns=_returns("spy"), signal_day=SIGNAL_DAY),
        "LEAD": _rows(base=100.0, returns=_returns("leader"), signal_day=SIGNAL_DAY),
        "FADE": _rows(base=100.0, returns=_returns("faded"), signal_day=SIGNAL_DAY),
    }


def _sector_entries() -> dict[str, dict]:
    return {
        ticker: {
            "sector": "Technology",
            "industry": "Semiconductors",
            "sector_coverage_status": "ok",
        }
        for ticker in ["LEAD", "FADE"]
    }


def test_snapshot_requires_same_day_core_flow_without_orders() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][SIGNAL_DAY]["date"]

    no_flow = build_fiftytwo_week_high_proximity_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[],
        sector_entries=_sector_entries(),
        state=empty_fiftytwo_week_high_proximity_state(),
        persist=False,
    )
    with_flow = build_fiftytwo_week_high_proximity_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "CORE", "strategy": "trend_long"}],
        sector_entries=_sector_entries(),
        state=empty_fiftytwo_week_high_proximity_state(),
        persist=False,
    )

    assert no_flow["candidate_count"] == 0
    assert with_flow["candidate_count"] == 1
    assert with_flow["new_pending_count"] == 1
    assert with_flow["trade_enabled"] is False
    assert with_flow["production_impact"]["alters_orders"] is False
    candidate = with_flow["candidates"][0]
    assert candidate["ticker"] == "LEAD"
    assert candidate["rule_version"] == RULE_VERSION
    assert candidate["source_rule_version"] == SOURCE_RULE_VERSION
    assert candidate["candidate_proximity_to_52w_high"] >= 0.97
    assert candidate["core_flow_confirmation"]["same_day_ab_overlap"] is True


def test_far_from_52_week_high_is_not_a_candidate() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][SIGNAL_DAY]["date"]

    snapshot = build_fiftytwo_week_high_proximity_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker={"SPY": ohlcv["SPY"], "FADE": ohlcv["FADE"]},
        core_entries=[{"ticker": "CORE"}],
        sector_entries={"FADE": _sector_entries()["FADE"]},
        state=empty_fiftytwo_week_high_proximity_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["raw_candidate_count"] == 0


def test_insufficient_history_fails_closed() -> None:
    ohlcv = _ohlcv()
    short = {ticker: rows[-100:] for ticker, rows in ohlcv.items()}
    signal_day = short["SPY"][-1]["date"]

    snapshot = build_fiftytwo_week_high_proximity_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=short,
        core_entries=[{"ticker": "CORE"}],
        sector_entries=_sector_entries(),
        state=empty_fiftytwo_week_high_proximity_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["raw_candidate_count"] == 0


def test_same_ticker_core_overlap_is_excluded() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][SIGNAL_DAY]["date"]

    snapshot = build_fiftytwo_week_high_proximity_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "LEAD", "strategy": "trend_long"}],
        sector_entries=_sector_entries(),
        state=empty_fiftytwo_week_high_proximity_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    context = snapshot["fiftytwo_week_high_context"]
    assert context["raw_candidates_excluded_same_ticker_core_overlap"] == 1


def test_historical_replay_and_daily_snapshot_share_candidate() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][SIGNAL_DAY]["date"]
    windows = {
        "fixture": {"start": signal_day, "end": ohlcv["SPY"][SIGNAL_DAY + 10]["date"]}
    }

    trades, audit = build_fiftytwo_week_high_proximity_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date={signal_day: [{"ticker": "CORE"}]},
        windows=windows,
        sector_entries=_sector_entries(),
    )
    snapshot = build_fiftytwo_week_high_proximity_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "CORE"}],
        sector_entries=_sector_entries(),
        state=empty_fiftytwo_week_high_proximity_state(),
        persist=False,
    )

    assert len(trades) == 1
    assert trades[0]["ticker"] == snapshot["candidates"][0]["ticker"] == "LEAD"
    assert trades[0]["decision_id"] == snapshot["candidates"][0]["decision_id"]
    assert trades[0]["rule_version"] == snapshot["rule_version"] == RULE_VERSION
    assert audit["selected_by_window"]["fixture"] == 1


def test_daily_snapshot_advances_pending_to_closed_using_same_fill_model(tmp_path) -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][SIGNAL_DAY]["date"]
    exit_day = ohlcv["SPY"][SIGNAL_DAY + 10]["date"]
    state_path = tmp_path / "state.json"
    snapshot_log_path = tmp_path / "snapshots.jsonl"

    trades, _audit = build_fiftytwo_week_high_proximity_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date={signal_day: [{"ticker": "CORE"}]},
        windows={"fixture": {"start": signal_day, "end": exit_day}},
        sector_entries=_sector_entries(),
    )
    signal_snapshot = build_fiftytwo_week_high_proximity_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "CORE"}],
        sector_entries=_sector_entries(),
        state_path=state_path,
        snapshot_log_path=snapshot_log_path,
        persist=True,
    )
    closed_snapshot = {}
    for day_idx in range(SIGNAL_DAY + 1, SIGNAL_DAY + 11):
        closed_snapshot = build_fiftytwo_week_high_proximity_snapshot(
            as_of=ohlcv["SPY"][day_idx]["date"],
            ohlcv_by_ticker=ohlcv,
            core_entries=[],
            sector_entries=_sector_entries(),
            state_path=state_path,
            snapshot_log_path=snapshot_log_path,
            persist=True,
        )

    assert signal_snapshot["pending_count"] == 1
    assert closed_snapshot["asof_date"] == exit_day
    assert closed_snapshot["closed_count_today"] == 1
    closed = closed_snapshot["closed_positions_this_run"][0]
    assert closed["ticker"] == trades[0]["ticker"] == "LEAD"
    assert closed["entry_date"] == trades[0]["entry_date"]
    assert closed["exit_date"] == trades[0]["exit_date"]
    assert closed["pnl_pct_net"] == trades[0]["pnl_pct_net"]
    assert closed["trade_enabled"] is False


def test_kill_switch_blocks_new_pending_entries_without_orders(tmp_path) -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][SIGNAL_DAY]["date"]

    # committed capital = 10 positions x $4,000 = $40,000.
    # kill limit = 8% = $3,200 realized peak-to-trough drawdown.
    losing_state = empty_fiftytwo_week_high_proximity_state()
    losing_state["closed_positions"] = [
        {
            "decision_id": f"FIFTYTWO_WEEK_HIGH_PROXIMITY_CORE_FLOW_PAPER:loss:{idx}",
            "ticker": f"LOSS{idx}",
            "exit_date": ohlcv["SPY"][200 + idx]["date"],
            "pnl": -400.0,
        }
        for idx in range(9)
    ]

    kill = evaluate_fiftytwo_week_high_kill_switch(losing_state["closed_positions"])
    assert kill["triggered"] is True
    assert "realized_drawdown_kill_limit" in kill["reasons"]
    assert kill["alters_orders"] is False

    snapshot = build_fiftytwo_week_high_proximity_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "CORE"}],
        sector_entries=_sector_entries(),
        state=losing_state,
        persist=False,
    )

    assert snapshot["kill_switch"]["triggered"] is True
    assert snapshot["candidate_count"] == 1  # signal still observed
    assert snapshot["new_pending_count"] == 0  # but no new paper entry
    assert snapshot["trade_enabled"] is False


def test_kill_switch_stays_armed_on_small_losses() -> None:
    closed = [
        {"ticker": "OK1", "exit_date": "2026-01-05", "pnl": -200.0},
        {"ticker": "OK2", "exit_date": "2026-01-12", "pnl": 350.0},
        {"ticker": "OK3", "exit_date": "2026-01-20", "pnl": -150.0},
    ]
    kill = evaluate_fiftytwo_week_high_kill_switch(closed)
    assert kill["triggered"] is False
    assert kill["status"] == "armed"
    assert kill["metrics"]["closed_trades"] == 3
