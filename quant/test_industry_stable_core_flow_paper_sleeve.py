from __future__ import annotations

from datetime import date, timedelta

from quant.industry_stable_core_flow_paper_sleeve import (
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_industry_stable_core_flow_historical_trades,
    build_industry_stable_core_flow_snapshot,
    empty_industry_stable_core_flow_state,
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


def _returns(kind: str, days: int = 86, signal_day: int = 70) -> list[float]:
    values = [0.001 for _ in range(days)]
    if kind == "spy":
        values[signal_day] = 0.001
        return values
    if kind == "member":
        for idx in range(signal_day - 20, signal_day + 1):
            values[idx] = 0.0032
        values[signal_day] = 0.004
        return values
    if kind == "leader":
        for idx in range(signal_day - 20, signal_day + 1):
            values[idx] = 0.0046
        values[signal_day] = 0.010
        return values
    raise AssertionError(kind)


def _ohlcv() -> dict[str, list[dict]]:
    signal_day = 70
    payload = {"SPY": _rows(base=100.0, returns=_returns("spy"), signal_day=signal_day)}
    for ticker in ["MEM1", "MEM2", "MEM3", "MEM4", "MEM5"]:
        payload[ticker] = _rows(
            base=80.0,
            returns=_returns("member"),
            signal_day=signal_day,
        )
    payload["LEAD"] = _rows(
        base=90.0,
        returns=_returns("leader"),
        signal_day=signal_day,
    )
    return payload


def _sector_entries() -> dict[str, dict]:
    return {
        ticker: {
            "sector": "Technology",
            "industry": "Semiconductors",
            "sector_coverage_status": "ok",
        }
        for ticker in ["MEM1", "MEM2", "MEM3", "MEM4", "MEM5", "LEAD"]
    }


def test_snapshot_requires_same_day_core_flow_without_orders() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]

    no_flow = build_industry_stable_core_flow_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[],
        sector_entries=_sector_entries(),
        state=empty_industry_stable_core_flow_state(),
        persist=False,
    )
    with_flow = build_industry_stable_core_flow_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "CORE", "strategy": "trend_long"}],
        sector_entries=_sector_entries(),
        state=empty_industry_stable_core_flow_state(),
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
    assert candidate["core_flow_confirmation"]["same_day_ab_overlap"] is True


def test_same_ticker_core_overlap_is_excluded() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]

    snapshot = build_industry_stable_core_flow_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "LEAD", "strategy": "trend_long"}],
        sector_entries=_sector_entries(),
        state=empty_industry_stable_core_flow_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    context = snapshot["industry_stable_core_flow_context"]
    assert context["raw_candidates_excluded_same_ticker_core_overlap"] == 1


def test_historical_replay_and_daily_snapshot_share_candidate() -> None:
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]
    windows = {"fixture": {"start": signal_day, "end": ohlcv["SPY"][80]["date"]}}

    trades, audit = build_industry_stable_core_flow_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date={signal_day: [{"ticker": "CORE"}]},
        windows=windows,
        sector_entries=_sector_entries(),
    )
    snapshot = build_industry_stable_core_flow_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "CORE"}],
        sector_entries=_sector_entries(),
        state=empty_industry_stable_core_flow_state(),
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

    trades, _audit = build_industry_stable_core_flow_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date={signal_day: [{"ticker": "CORE"}]},
        windows={"fixture": {"start": signal_day, "end": exit_day}},
        sector_entries=_sector_entries(),
    )
    signal_snapshot = build_industry_stable_core_flow_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "CORE"}],
        sector_entries=_sector_entries(),
        state_path=state_path,
        snapshot_log_path=snapshot_log_path,
        persist=True,
    )
    closed_snapshot = {}
    for day_idx in range(71, 81):
        closed_snapshot = build_industry_stable_core_flow_snapshot(
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


def test_sector_entries_fall_back_to_sector_cache_for_governance_feed(monkeypatch) -> None:
    import types

    from quant import industry_stable_core_flow_paper_sleeve as sleeve_module

    monkeypatch.setattr(
        sleeve_module,
        "broad_market_sector_map",
        types.SimpleNamespace(load_cache=lambda *args, **kwargs: {"entries": _sector_entries()}),
    )
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]
    tickers = ["MEM1", "MEM2", "MEM3", "MEM4", "MEM5", "LEAD"]
    governance_universe = {
        "status": "universe_state_observation_feed",
        "tickers": sorted(tickers),
        "records": {
            ticker: {
                "ticker": ticker,
                "title": f"{ticker} Inc",
                "status": "active",
                "theme": "space",
            }
            for ticker in tickers
        },
    }

    snapshot = build_industry_stable_core_flow_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "CORE", "strategy": "trend_long"}],
        candidate_universe=governance_universe,
        state=empty_industry_stable_core_flow_state(),
        persist=False,
    )

    assert snapshot.get("error") is None
    assert snapshot["candidate_count"] == 1
    assert snapshot["candidates"][0]["ticker"] == "LEAD"
