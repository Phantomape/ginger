from __future__ import annotations

from datetime import date, timedelta

from quant.rolling_corr_peer_shock_paper_sleeve import (
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_rolling_corr_peer_shock_historical_trades,
    build_rolling_corr_peer_shock_paper_sleeve_snapshot,
    empty_rolling_corr_peer_shock_paper_state,
)


def _rows(
    *,
    base: float,
    normal_return: float,
    shock_day: int,
    shock_return: float,
    days: int = 90,
    volume: float = 1_000_000.0,
    shock_volume: float | None = None,
) -> list[dict]:
    current = date(2026, 1, 1)
    rows = []
    close = base
    while len(rows) < days:
        if current.weekday() < 5:
            idx = len(rows)
            base_ret = normal_return + (((idx % 7) - 3) * 0.0002)
            ret = shock_return if idx == shock_day else base_ret
            close *= 1.0 + ret
            open_ = close / (1.0 + max(ret * 0.55, -0.02))
            low = min(open_, close) * 0.992
            high = max(open_, close) * 1.006
            rows.append(
                {
                    "date": current.isoformat(),
                    "open": round(open_, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "volume": shock_volume if idx == shock_day and shock_volume else volume,
                }
            )
        current += timedelta(days=1)
    return rows


def _ohlcv() -> dict[str, list[dict]]:
    shock_day = 70
    return {
        "SPY": _rows(
            base=100.0,
            normal_return=0.001,
            shock_day=shock_day,
            shock_return=0.001,
            volume=50_000_000.0,
        ),
        "PEER": _rows(
            base=120.0,
            normal_return=0.002,
            shock_day=shock_day,
            shock_return=0.08,
            volume=1_200_000.0,
            shock_volume=2_800_000.0,
        ),
        "LAG": _rows(
            base=80.0,
            normal_return=0.002,
            shock_day=shock_day,
            shock_return=0.01,
            volume=1_300_000.0,
            shock_volume=1_500_000.0,
        ),
        "CORE": _rows(
            base=60.0,
            normal_return=0.0015,
            shock_day=shock_day,
            shock_return=0.012,
            volume=1_000_000.0,
        ),
    }


def _sector_entries() -> dict[str, dict]:
    return {
        "PEER": {"sector": "Technology", "industry": "Semiconductors", "status": "ok"},
        "LAG": {"sector": "Technology", "industry": "Semiconductors", "status": "ok"},
        "CORE": {"sector": "Technology", "industry": "Software", "status": "ok"},
    }


def test_snapshot_adds_core_flow_confirmed_peer_shock_candidate_without_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][70]["date"]

    snapshot = build_rolling_corr_peer_shock_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "CORE", "entry_signal": "A"}],
        sector_entries=_sector_entries(),
        state=empty_rolling_corr_peer_shock_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert len(snapshot["new_pending_entries"]) == 1
    assert len(snapshot["pending_entries"]) == snapshot["pending_count"] == 1
    assert snapshot["pending_entries"][0]["paper_notional_usd"] == 4_000.0
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False
    assert snapshot["production_impact"]["alters_signal_generation"] is False
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "LAG"
    assert candidate["peer_ticker"] == "PEER"
    assert candidate["rule_version"] == RULE_VERSION
    assert candidate["source_rule_version"] == SOURCE_RULE_VERSION
    assert candidate["same_day_ab_overlap"] is True
    assert candidate["same_ticker_ab_overlap"] is False
    assert candidate["paper_notional_usd"] == 4_000.0


def test_candidate_requires_same_day_core_flow_confirmation():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][70]["date"]

    snapshot = build_rolling_corr_peer_shock_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        core_entries=[],
        sector_entries=_sector_entries(),
        state=empty_rolling_corr_peer_shock_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["peer_shock_context"]["raw_candidates_after_core_flow_filter"] == 0
    assert snapshot["trade_enabled"] is False


def test_historical_replay_and_daily_snapshot_share_candidate_rule_versions():
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]
    windows = {"fixture": {"start": signal_day, "end": ohlcv["SPY"][72]["date"]}}
    core_entries = {signal_day: [{"ticker": "CORE", "entry_signal": "B"}]}

    trades, audit = build_rolling_corr_peer_shock_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date=core_entries,
        windows=windows,
        sector_entries=_sector_entries(),
    )
    snapshot = build_rolling_corr_peer_shock_paper_sleeve_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=core_entries[signal_day],
        sector_entries=_sector_entries(),
        state=empty_rolling_corr_peer_shock_paper_state(),
        persist=False,
    )

    assert trades
    assert trades[0]["ticker"] == snapshot["candidates"][0]["ticker"] == "LAG"
    assert trades[0]["rule_version"] == snapshot["candidates"][0]["rule_version"] == RULE_VERSION
    assert trades[0]["source_rule_version"] == SOURCE_RULE_VERSION
    assert audit["selected_by_window"]["fixture"] == 1
    assert snapshot["production_impact"]["trade_enabled"] is False


def test_daily_snapshot_advances_pending_to_closed_using_historical_fill_model(tmp_path):
    ohlcv = _ohlcv()
    signal_day = ohlcv["SPY"][70]["date"]
    exit_day = ohlcv["SPY"][80]["date"]
    state_path = tmp_path / "state.json"
    snapshot_log_path = tmp_path / "snapshots.jsonl"
    core_entries = {signal_day: [{"ticker": "CORE", "entry_signal": "B"}]}

    trades, _audit = build_rolling_corr_peer_shock_historical_trades(
        ohlcv_by_ticker=ohlcv,
        core_entries_by_date=core_entries,
        windows={"fixture": {"start": signal_day, "end": exit_day}},
        sector_entries=_sector_entries(),
    )
    signal_snapshot = build_rolling_corr_peer_shock_paper_sleeve_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=core_entries[signal_day],
        sector_entries=_sector_entries(),
        state_path=state_path,
        snapshot_log_path=snapshot_log_path,
        persist=True,
    )
    closed_snapshot = build_rolling_corr_peer_shock_paper_sleeve_snapshot(
        as_of=exit_day,
        ohlcv_by_ticker=ohlcv,
        core_entries=[],
        sector_entries=_sector_entries(),
        state_path=state_path,
        snapshot_log_path=snapshot_log_path,
        persist=True,
    )

    assert signal_snapshot["pending_count"] == 1
    assert closed_snapshot["closed_count_today"] == 1
    assert closed_snapshot["open_position_count"] == 0
    assert closed_snapshot["realized_pnl_to_date"] == trades[0]["pnl"]
    closed = closed_snapshot["closed_positions_this_run"][0]
    assert closed["ticker"] == trades[0]["ticker"] == "LAG"
    assert closed["entry_date"] == trades[0]["entry_date"]
    assert closed["exit_date"] == trades[0]["exit_date"]
    assert closed["pnl_pct_net"] == trades[0]["pnl_pct_net"]
    assert closed["trade_enabled"] is False


def _governance_universe(tickers: list[str]) -> dict:
    return {
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


def test_snapshot_accepts_dataframe_ohlcv_from_daily_run() -> None:
    pd = __import__("pandas")
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][70]["date"]
    frames = {
        ticker: pd.DataFrame(
            [
                {
                    "Open": row["open"],
                    "High": row["high"],
                    "Low": row["low"],
                    "Close": row["close"],
                    "Volume": row["volume"],
                }
                for row in rows
            ],
            index=pd.to_datetime([row["date"] for row in rows]),
        )
        for ticker, rows in ohlcv.items()
    }

    snapshot = build_rolling_corr_peer_shock_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=frames,
        core_entries=[{"ticker": "CORE", "entry_signal": "A"}],
        sector_entries=_sector_entries(),
        state=empty_rolling_corr_peer_shock_paper_state(),
        persist=False,
    )

    assert snapshot.get("error") is None
    assert snapshot["candidate_count"] == 1
    assert snapshot["candidates"][0]["ticker"] == "LAG"


def test_sector_entries_fall_back_to_sector_cache_for_governance_feed(monkeypatch) -> None:
    import types

    from quant import rolling_corr_peer_shock_paper_sleeve as sleeve_module

    monkeypatch.setattr(
        sleeve_module,
        "broad_market_sector_map",
        types.SimpleNamespace(load_cache=lambda *args, **kwargs: {"entries": _sector_entries()}),
    )
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][70]["date"]

    snapshot = build_rolling_corr_peer_shock_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        core_entries=[{"ticker": "CORE", "entry_signal": "A"}],
        candidate_universe=_governance_universe(["PEER", "LAG", "CORE"]),
        state=empty_rolling_corr_peer_shock_paper_state(),
        persist=False,
    )

    assert snapshot.get("error") is None
    assert snapshot["candidate_count"] == 1
    assert snapshot["candidates"][0]["ticker"] == "LAG"
