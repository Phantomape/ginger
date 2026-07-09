from __future__ import annotations

from datetime import date, timedelta

from quant.turn_of_month_liquid_leadership_paper_sleeve import (
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_turn_of_month_liquid_leadership_historical_trades,
    build_turn_of_month_liquid_leadership_snapshot,
    empty_turn_of_month_liquid_leadership_state,
    prep_and_build_turn_of_month_liquid_leadership_snapshot,
)


def _business_dates(days: int) -> list[str]:
    current = date(2025, 12, 1)
    out: list[str] = []
    while len(out) < days:
        if current.weekday() < 5:
            out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def _signal_index(dates: list[str]) -> int:
    for idx, day in enumerate(dates):
        previous_month = dates[idx - 1][:7] if idx > 0 else None
        is_first_trading_day = previous_month is not None and day[:7] != previous_month
        if idx > 65 and is_first_trading_day and idx + 10 < len(dates):
            return idx
    raise AssertionError("missing first trading day fixture")


def _rows(
    *,
    base: float,
    returns: list[float],
    signal_day: int,
    volume: float = 1_000_000.0,
) -> list[dict]:
    rows = []
    close = base
    dates = _business_dates(len(returns))
    for idx, day in enumerate(dates):
        prior_close = close
        ret = returns[idx]
        open_ = prior_close
        close = prior_close * (1.0 + ret)
        if idx == signal_day:
            low = min(open_, close) * 0.992
            high = close * 1.003
        else:
            low = close * 0.990
            high = close * 1.010
        rows.append(
            {
                "date": day,
                "open": round(open_, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": volume,
            }
        )
    return rows


def _returns(kind: str, days: int = 125) -> list[float]:
    dates = _business_dates(days)
    signal_day = _signal_index(dates)
    values = [0.001 for _ in range(days)]
    if kind == "spy":
        values[signal_day] = 0.001
        return values
    if kind == "leader":
        for idx in range(signal_day - 65, signal_day):
            values[idx] = 0.0028
        values[signal_day] = 0.014
        values[signal_day + 1 : signal_day + 11] = [0.004] * 10
        return values
    if kind == "secondary":
        for idx in range(signal_day - 65, signal_day):
            values[idx] = 0.0022
        values[signal_day] = 0.010
        return values
    raise AssertionError(kind)


def _returns_for_signal(kind: str, signal_day: int, days: int = 110) -> list[float]:
    values = [0.001 for _ in range(days)]
    if kind == "spy":
        values[signal_day] = 0.001
        return values
    if kind == "leader":
        for idx in range(signal_day - 65, signal_day):
            values[idx] = 0.0028
        values[signal_day] = 0.014
        values[signal_day + 1 : signal_day + 11] = [0.004] * 10
        return values
    if kind == "secondary":
        for idx in range(signal_day - 65, signal_day):
            values[idx] = 0.0022
        values[signal_day] = 0.010
        return values
    raise AssertionError(kind)


def _ohlcv(days: int = 125) -> dict[str, list[dict]]:
    dates = _business_dates(days)
    signal_day = _signal_index(dates)
    return {
        "SPY": _rows(base=100.0, returns=_returns("spy", days), signal_day=signal_day),
        "LEAD": _rows(base=90.0, returns=_returns("leader", days), signal_day=signal_day),
        "ALT": _rows(base=80.0, returns=_returns("secondary", days), signal_day=signal_day),
    }


def _ohlcv_for_signal(signal_day: int, days: int = 110) -> dict[str, list[dict]]:
    return {
        "SPY": _rows(
            base=100.0,
            returns=_returns_for_signal("spy", signal_day, days),
            signal_day=signal_day,
        ),
        "LEAD": _rows(
            base=90.0,
            returns=_returns_for_signal("leader", signal_day, days),
            signal_day=signal_day,
        ),
        "ALT": _rows(
            base=80.0,
            returns=_returns_for_signal("secondary", signal_day, days),
            signal_day=signal_day,
        ),
    }


def _universe() -> dict:
    return {
        "status": "test_broad_market_universe",
        "tickers": ["LEAD", "ALT"],
        "records": {
            ticker: {
                "sector": "Technology",
                "industry": "Software",
            }
            for ticker in ["LEAD", "ALT"]
        },
    }


def test_snapshot_creates_default_off_pending_without_orders() -> None:
    ohlcv = _ohlcv()
    dates = [row["date"] for row in ohlcv["SPY"]]
    signal_day = dates[_signal_index(dates)]
    truncated = {ticker: rows[: _signal_index(dates) + 1] for ticker, rows in ohlcv.items()}

    snapshot = build_turn_of_month_liquid_leadership_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=truncated,
        candidate_universe=_universe(),
        calendar_dates=dates,
        state=empty_turn_of_month_liquid_leadership_state(),
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
    assert candidate["candidate_month_label"] == "first_trading_day_1"


def test_historical_replay_and_daily_snapshot_share_candidate_decision() -> None:
    ohlcv = _ohlcv()
    dates = [row["date"] for row in ohlcv["SPY"]]
    signal_day = dates[_signal_index(dates)]
    exit_day = dates[_signal_index(dates) + 10]

    trades, audit = build_turn_of_month_liquid_leadership_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date={signal_day: [{"ticker": "CORE"}]},
        windows={"fixture": {"start": signal_day, "end": exit_day}},
        candidate_universe=_universe(),
        calendar_dates=dates,
    )
    snapshot = build_turn_of_month_liquid_leadership_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=_universe(),
        core_entries=[{"ticker": "CORE", "date": signal_day}],
        calendar_dates=dates,
        state=empty_turn_of_month_liquid_leadership_state(),
        persist=False,
    )

    assert len(trades) == 1
    assert trades[0]["ticker"] == snapshot["candidates"][0]["ticker"] == "LEAD"
    assert trades[0]["decision_id"] == snapshot["candidates"][0]["decision_id"]
    assert audit["selected_by_window"]["fixture"] == 1


def test_daily_snapshot_does_not_infer_month_end_from_truncated_ohlcv() -> None:
    ohlcv = _ohlcv()
    dates = [row["date"] for row in ohlcv["SPY"]]
    as_of_idx = _signal_index(dates) + 7
    as_of = dates[as_of_idx]
    truncated = {ticker: rows[: as_of_idx + 1] for ticker, rows in ohlcv.items()}

    fail_closed = build_turn_of_month_liquid_leadership_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=truncated,
        candidate_universe=_universe(),
        state=empty_turn_of_month_liquid_leadership_state(),
        persist=False,
    )
    explicit_month_end = build_turn_of_month_liquid_leadership_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=truncated,
        candidate_universe=_universe(),
        known_month_end_dates={as_of},
        state=empty_turn_of_month_liquid_leadership_state(),
        persist=False,
    )

    assert fail_closed["candidate_count"] == 0
    assert fail_closed["context_scan"]["turn_of_month_days"] == 0
    assert explicit_month_end["context_scan"]["turn_of_month_days"] == 1


def test_daily_prep_marks_actual_last_trading_day_without_future_ohlcv() -> None:
    dates = _business_dates(110)
    signal_day = dates.index("2026-03-31")
    as_of = dates[signal_day]
    ohlcv = _ohlcv_for_signal(signal_day, days=len(dates))
    truncated = {ticker: rows[: signal_day + 1] for ticker, rows in ohlcv.items()}

    fail_closed = build_turn_of_month_liquid_leadership_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=truncated,
        candidate_universe=_universe(),
        state=empty_turn_of_month_liquid_leadership_state(),
        persist=False,
    )
    repaired = prep_and_build_turn_of_month_liquid_leadership_snapshot(
        as_of=as_of,
        broad_market_ohlcv=truncated,
        broad_market_candidate_universe=_universe(),
        state=empty_turn_of_month_liquid_leadership_state(),
        persist=False,
    )

    assert fail_closed["candidate_count"] == 0
    assert fail_closed["context_scan"]["turn_of_month_days"] == 0
    assert repaired["candidate_count"] == 1
    assert repaired["new_pending_count"] == 1
    assert repaired["candidates"][0]["ticker"] == "LEAD"
    assert repaired["candidates"][0]["candidate_month_label"] == "last_trading_day"
    assert repaired["context_scan"]["month_end_label_policy"] == (
        "explicit_known_month_end_dates_only_fail_closed"
    )
    assert repaired["context_scan"]["month_label_distribution"] == {
        "last_trading_day": 1
    }


def test_daily_snapshot_advances_pending_to_closed_using_same_fill_model(tmp_path) -> None:
    ohlcv = _ohlcv()
    dates = [row["date"] for row in ohlcv["SPY"]]
    signal_idx = _signal_index(dates)
    signal_day = dates[signal_idx]
    exit_day = dates[signal_idx + 10]
    state_path = tmp_path / "state.json"
    snapshot_log_path = tmp_path / "snapshots.jsonl"

    trades, _audit = build_turn_of_month_liquid_leadership_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date={signal_day: []},
        windows={"fixture": {"start": signal_day, "end": exit_day}},
        candidate_universe=_universe(),
        calendar_dates=dates,
    )
    signal_snapshot = build_turn_of_month_liquid_leadership_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=_universe(),
        calendar_dates=dates,
        state_path=state_path,
        snapshot_log_path=snapshot_log_path,
        persist=True,
    )
    closed_snapshot = {}
    for day_idx in range(signal_idx + 1, signal_idx + 11):
        closed_snapshot = build_turn_of_month_liquid_leadership_snapshot(
            as_of=dates[day_idx],
            ohlcv_by_ticker=ohlcv,
            candidate_universe=_universe(),
            calendar_dates=dates,
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
