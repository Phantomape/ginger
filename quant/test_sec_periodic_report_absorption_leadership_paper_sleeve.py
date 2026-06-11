from __future__ import annotations

from datetime import date, timedelta

from quant.experiments.exp_20260611_012_sec_periodic_report_absorption_helper import (
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_sec_periodic_report_absorption_historical_trades,
    build_sec_periodic_report_absorption_leadership_snapshot,
    empty_sec_periodic_report_absorption_leadership_state,
)


def _business_dates(days: int) -> list[str]:
    current = date(2026, 1, 1)
    out: list[str] = []
    while len(out) < days:
        if current.weekday() < 5:
            out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def _returns(kind: str, days: int = 88, signal_day: int = 70) -> list[float]:
    values = [0.001 for _ in range(days)]
    if kind == "spy":
        values[signal_day] = 0.002
        return values
    if kind == "qqq":
        values[signal_day] = 0.003
        return values
    if kind == "leader":
        for idx in range(signal_day - 60, signal_day):
            values[idx] = 0.002
        values[signal_day] = 0.030
        values[signal_day + 1 : signal_day + 11] = [0.004] * 10
        return values
    if kind == "alt":
        values[signal_day] = 0.012
        return values
    raise AssertionError(kind)


def _rows(
    *,
    base: float,
    returns: list[float],
    signal_day: int,
    volume: float = 1_000_000.0,
) -> list[dict]:
    rows = []
    close = base
    days = _business_dates(len(returns))
    for idx, day in enumerate(days):
        prior_close = close
        ret = returns[idx]
        open_ = prior_close
        close = prior_close * (1.0 + ret)
        if idx == signal_day:
            low = open_ * 0.995
            high = close * 1.003
            volume_mult = 1.20
        else:
            low = min(open_, close) * 0.995
            high = max(open_, close) * 1.005
            volume_mult = 1.0
        rows.append(
            {
                "date": day,
                "open": round(open_, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": volume * volume_mult,
            }
        )
    return rows


def _ohlcv(days: int = 88) -> dict[str, list[dict]]:
    signal_day = 70
    return {
        "SPY": _rows(
            base=100.0,
            returns=_returns("spy", days, signal_day),
            signal_day=signal_day,
        ),
        "QQQ": _rows(
            base=100.0,
            returns=_returns("qqq", days, signal_day),
            signal_day=signal_day,
        ),
        "LEAD": _rows(
            base=90.0,
            returns=_returns("leader", days, signal_day),
            signal_day=signal_day,
            volume=900_000.0,
        ),
        "ALT": _rows(
            base=80.0,
            returns=_returns("alt", days, signal_day),
            signal_day=signal_day,
            volume=800_000.0,
        ),
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


def _events(signal_day: str) -> list[dict]:
    return [
        {
            "ticker": "LEAD",
            "form_type": "10-Q",
            "form_base": "10-Q",
            "filing_date": signal_day,
            "usable_trade_date": signal_day,
            "accepted_at": f"{signal_day}T20:10:00",
            "accession_number": "0000000000-26-000001",
            "size": 15_000_000,
            "pit_safe_flag": True,
        },
        {
            "ticker": "ALT",
            "form_type": "10-K",
            "form_base": "10-K",
            "filing_date": signal_day,
            "usable_trade_date": signal_day,
            "accepted_at": f"{signal_day}T20:11:00",
            "accession_number": "0000000000-26-000002",
            "size": 24_000_000,
            "pit_safe_flag": True,
        },
    ]


def test_snapshot_creates_default_off_pending_without_future_data_or_orders() -> None:
    full_ohlcv = _ohlcv()
    signal_day = full_ohlcv["SPY"][70]["date"]
    truncated = {ticker: rows[:71] for ticker, rows in full_ohlcv.items()}

    snapshot = build_sec_periodic_report_absorption_leadership_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=truncated,
        sec_filing_events=_events(signal_day),
        sector_entries=_sector_entries(),
        state=empty_sec_periodic_report_absorption_leadership_state(),
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

    trades, audit = build_sec_periodic_report_absorption_historical_trades(
        ohlcv_by_ticker=ohlcv,
        sec_filing_events=_events(signal_day),
        core_entries_by_date={signal_day: [{"ticker": "CORE"}]},
        windows=windows,
        sector_entries=_sector_entries(),
    )
    snapshot = build_sec_periodic_report_absorption_leadership_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        sec_filing_events=_events(signal_day),
        core_entries=[{"ticker": "CORE"}],
        sector_entries=_sector_entries(),
        state=empty_sec_periodic_report_absorption_leadership_state(),
        persist=False,
    )

    assert len(trades) == 1
    assert trades[0]["ticker"] == snapshot["candidates"][0]["ticker"] == "LEAD"
    assert trades[0]["decision_id"] == snapshot["candidates"][0]["decision_id"]
    assert audit["selected_by_window"]["fixture"] == 1


def test_daily_snapshot_advances_pending_to_closed_using_same_fill_model(tmp_path) -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]
    exit_day = ohlcv["SPY"][80]["date"]
    state_path = tmp_path / "state.json"
    snapshot_log_path = tmp_path / "snapshots.jsonl"

    trades, _audit = build_sec_periodic_report_absorption_historical_trades(
        ohlcv_by_ticker=ohlcv,
        sec_filing_events=_events(signal_day),
        core_entries_by_date={signal_day: []},
        windows={"fixture": {"start": signal_day, "end": exit_day}},
        sector_entries=_sector_entries(),
    )
    build_sec_periodic_report_absorption_leadership_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        sec_filing_events=_events(signal_day),
        sector_entries=_sector_entries(),
        state_path=state_path,
        snapshot_log_path=snapshot_log_path,
        persist=True,
    )

    closed_snapshot = {}
    for row in ohlcv["SPY"][71:81]:
        closed_snapshot = build_sec_periodic_report_absorption_leadership_snapshot(
            as_of=row["date"],
            ohlcv_by_ticker=ohlcv,
            sec_filing_events=[],
            sector_entries=_sector_entries(),
            state_path=state_path,
            snapshot_log_path=snapshot_log_path,
            persist=True,
        )

    assert closed_snapshot["asof_date"] == exit_day
    assert closed_snapshot["closed_count_today"] == 1
    assert closed_snapshot["closed_today"][0]["decision_id"] == trades[0]["decision_id"]
    assert closed_snapshot["closed_today"][0]["pnl"] == trades[0]["pnl"]


def test_missing_sec_events_fail_closed() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]

    snapshot = build_sec_periodic_report_absorption_leadership_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        sec_filing_events=None,
        sector_entries=_sector_entries(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["trade_enabled"] is False
    assert snapshot["error"] == "missing_sec_filing_events"
