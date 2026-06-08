from __future__ import annotations

from datetime import date, timedelta

from quant.narrow_range_compression_breakout_paper_sleeve import (
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_narrow_range_compression_breakout_historical_trades,
    build_narrow_range_compression_breakout_snapshot,
    empty_narrow_range_compression_breakout_state,
)


def _business_dates(days: int) -> list[str]:
    current = date(2026, 1, 1)
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
    volume: float = 1_000_000.0,
) -> list[dict]:
    rows = []
    close = base
    for idx, day in enumerate(_business_dates(len(returns))):
        prior_close = close
        ret = returns[idx]
        open_ = prior_close
        close = prior_close * (1.0 + ret)
        if idx == signal_day:
            low = open_ * 0.990
            high = close * 1.005
        elif signal_day - 10 <= idx < signal_day:
            low = close * 0.996
            high = close * 1.004
        else:
            low = close * 0.985
            high = close * 1.015
        rows.append(
            {
                "date": day,
                "open": round(open_, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": volume * (1.45 if idx == signal_day else 1.0),
            }
        )
    return rows


def _returns(kind: str, days: int = 88, signal_day: int = 70) -> list[float]:
    values = [0.001 for _ in range(days)]
    if kind == "spy":
        values[signal_day] = 0.001
        return values
    if kind == "leader":
        for idx in range(signal_day - 20, signal_day):
            values[idx] = 0.0025
        values[signal_day] = 0.012
        values[signal_day + 1 : signal_day + 11] = [0.004] * 10
        return values
    if kind == "secondary":
        for idx in range(signal_day - 20, signal_day):
            values[idx] = 0.0018
        values[signal_day] = 0.008
        return values
    raise AssertionError(kind)


def _ohlcv(days: int = 88) -> dict[str, list[dict]]:
    signal_day = 70
    return {
        "SPY": _rows(base=100.0, returns=_returns("spy", days), signal_day=signal_day),
        "LEAD": _rows(base=90.0, returns=_returns("leader", days), signal_day=signal_day),
        "ALT": _rows(base=80.0, returns=_returns("secondary", days), signal_day=signal_day),
    }


def _sector_entries() -> dict[str, dict]:
    return {
        ticker: {
            "sector": "Technology",
            "industry": "Software",
            "sector_coverage_status": "ok",
        }
        for ticker in ["LEAD", "ALT"]
    }


def test_snapshot_creates_default_off_pending_without_future_data_or_orders() -> None:
    full_ohlcv = _ohlcv()
    signal_day = full_ohlcv["SPY"][70]["date"]
    truncated = {ticker: rows[:71] for ticker, rows in full_ohlcv.items()}

    snapshot = build_narrow_range_compression_breakout_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=truncated,
        sector_entries=_sector_entries(),
        state=empty_narrow_range_compression_breakout_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["alters_orders"] is False
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "LEAD"
    assert candidate["rule_version"] == RULE_VERSION
    assert candidate["source_rule_version"] == SOURCE_RULE_VERSION


def test_historical_replay_and_daily_snapshot_share_candidate_decision() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]
    windows = {"fixture": {"start": signal_day, "end": ohlcv["SPY"][80]["date"]}}

    trades, audit = build_narrow_range_compression_breakout_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date={signal_day: [{"ticker": "CORE"}]},
        windows=windows,
        sector_entries=_sector_entries(),
    )
    snapshot = build_narrow_range_compression_breakout_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "CORE"}],
        sector_entries=_sector_entries(),
        state=empty_narrow_range_compression_breakout_state(),
        persist=False,
    )

    assert len(trades) == 1
    assert trades[0]["ticker"] == snapshot["candidates"][0]["ticker"] == "LEAD"
    assert trades[0]["decision_id"] == snapshot["candidates"][0]["decision_id"]
    assert audit["selected_by_window"]["fixture"] == 1


def test_historical_replay_uses_next_open_and_10_day_close_fill() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]
    exit_day = ohlcv["SPY"][80]["date"]

    trades, _audit = build_narrow_range_compression_breakout_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date={signal_day: []},
        windows={"fixture": {"start": signal_day, "end": exit_day}},
        sector_entries=_sector_entries(),
    )

    assert len(trades) == 1
    trade = trades[0]
    assert trade["entry_date"] == ohlcv["SPY"][71]["date"]
    assert trade["exit_date"] == exit_day
    assert trade["paper_status"] == "closed"
    assert trade["trade_enabled"] is False
    assert trade["pnl_pct_net"] > 0


def test_daily_snapshot_advances_pending_to_closed_using_same_fill_model(tmp_path) -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]
    exit_day = ohlcv["SPY"][80]["date"]
    state_path = tmp_path / "state.json"
    snapshot_log_path = tmp_path / "snapshots.jsonl"

    trades, _audit = build_narrow_range_compression_breakout_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date={signal_day: []},
        windows={"fixture": {"start": signal_day, "end": exit_day}},
        sector_entries=_sector_entries(),
    )
    signal_snapshot = build_narrow_range_compression_breakout_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        sector_entries=_sector_entries(),
        state_path=state_path,
        snapshot_log_path=snapshot_log_path,
        persist=True,
    )
    closed_snapshot = {}
    for day_idx in range(71, 81):
        closed_snapshot = build_narrow_range_compression_breakout_snapshot(
            as_of=ohlcv["SPY"][day_idx]["date"],
            ohlcv_by_ticker=ohlcv,
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
