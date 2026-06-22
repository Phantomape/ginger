from __future__ import annotations

from datetime import date, timedelta

from quant.experiments.exp_20260622_010_moomoo_daily_short_volume_activity_helper import (
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_moomoo_daily_short_volume_historical_trades,
    build_moomoo_daily_short_volume_paper_sleeve_snapshot,
    empty_moomoo_daily_short_volume_state,
)


def _business_dates(days: int) -> list[str]:
    current = date(2026, 1, 1)
    out: list[str] = []
    while len(out) < days:
        if current.weekday() < 5:
            out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def _rows(base: float, returns: list[float], *, volume: float = 1_000_000.0) -> list[dict]:
    rows = []
    close = base
    for idx, day in enumerate(_business_dates(len(returns))):
        prior = close
        ret = returns[idx]
        open_ = prior
        close = prior * (1.0 + ret)
        high = max(open_, close) * 1.006
        low = min(open_, close) * 0.994
        rows.append(
            {
                "Date": day,
                "Open": round(open_, 4),
                "High": round(high, 4),
                "Low": round(low, 4),
                "Close": round(close, 4),
                "Volume": volume,
            }
        )
    return rows


def _ohlcv(days: int = 90, signal_idx: int = 70) -> dict[str, list[dict]]:
    spy_returns = [0.001 for _ in range(days)]
    ticker_returns = [0.0015 for _ in range(days)]
    spy_returns[signal_idx] = 0.002
    ticker_returns[signal_idx] = 0.035
    ticker_returns[signal_idx + 1 : signal_idx + 11] = [0.004] * 10
    return {
        "SPY": _rows(100.0, spy_returns, volume=5_000_000.0),
        "MOOM": _rows(50.0, ticker_returns, volume=2_000_000.0),
    }


def _activity_rows(ohlcv: dict[str, list[dict]], signal_idx: int = 70) -> list[dict]:
    rows = []
    for idx, bar in enumerate(ohlcv["MOOM"][: signal_idx + 1]):
        ratio = 0.10
        total_short = 200_000
        if idx == signal_idx:
            ratio = 0.18
            total_short = 360_000
        rows.append(
            {
                "schema_version": "test",
                "source": "moomoo_get_daily_short_volume",
                "source_code": "US.MOOM",
                "ticker": "MOOM",
                "activity_date": bar["Date"],
                "total_shares_short": total_short,
                "volume": 2_000_000,
                "short_volume_ratio": ratio,
            }
        )
    return rows


def test_snapshot_creates_next_session_default_off_candidate() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["MOOM"][70]["Date"]
    snapshot = build_moomoo_daily_short_volume_paper_sleeve_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker={ticker: rows[:71] for ticker, rows in ohlcv.items()},
        activity_rows=_activity_rows(ohlcv),
        state=empty_moomoo_daily_short_volume_state(),
        persist=False,
    )

    assert snapshot["trade_enabled"] is False
    assert snapshot["candidate_count"] == 1
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "MOOM"
    assert candidate["date"] == signal_day
    assert candidate["usable_trade_date"] == ohlcv["MOOM"][71]["Date"]
    assert candidate["rule_version"] == RULE_VERSION
    assert candidate["source_rule_version"] == SOURCE_RULE_VERSION
    assert candidate["activity_only_not_positioning"] is True


def test_historical_replay_and_snapshot_share_decision_id() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["MOOM"][70]["Date"]
    windows = {"fixture": {"start": signal_day, "end": ohlcv["MOOM"][80]["Date"]}}

    trades, audit = build_moomoo_daily_short_volume_historical_trades(
        ohlcv_by_ticker=ohlcv,
        activity_rows=_activity_rows(ohlcv),
        core_entries_by_date={signal_day: []},
        windows=windows,
    )
    snapshot = build_moomoo_daily_short_volume_paper_sleeve_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        activity_rows=_activity_rows(ohlcv),
        state=empty_moomoo_daily_short_volume_state(),
        persist=False,
    )

    assert len(trades) == 1
    assert trades[0]["decision_id"] == snapshot["candidates"][0]["decision_id"]
    assert trades[0]["entry_date"] == ohlcv["MOOM"][71]["Date"]
    assert trades[0]["entry_date"] != trades[0]["signal_date"]
    assert trades[0]["exit_date"] == ohlcv["MOOM"][80]["Date"]
    assert audit["selected_by_window"]["fixture"] == 1


def test_same_ticker_core_overlap_is_rejected() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["MOOM"][70]["Date"]
    trades, audit = build_moomoo_daily_short_volume_historical_trades(
        ohlcv_by_ticker=ohlcv,
        activity_rows=_activity_rows(ohlcv),
        core_entries_by_date={signal_day: [{"ticker": "MOOM"}]},
        windows={"fixture": {"start": signal_day, "end": ohlcv["MOOM"][80]["Date"]}},
    )

    assert trades == []
    assert audit["raw_candidate_count_by_window"]["fixture"] == 1
    assert audit["rejected_count_by_window"]["fixture"] == 1
