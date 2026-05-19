from __future__ import annotations

from datetime import date, timedelta

from quant.broad_market_paper_sleeve import (
    build_broad_market_paper_candidates,
    build_broad_market_paper_sleeve_snapshot,
    build_broad_market_feature,
    candidate_passes_profile,
    empty_broad_market_paper_state,
)


def _rows(start_price: float, step: float, *, volume_last: float = 1500.0) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(62):
        close = start_price + step * idx
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": close * 0.99,
                "high": close,
                "low": close * 0.98,
                "close": close,
                "volume": volume_last if idx == 60 else 1000.0,
            }
        )
    return rows


def test_broad_market_feature_and_price_floor_gate():
    spy_rows = _rows(100.0, 0.02)
    high_price_rows = _rows(50.0, 0.35)
    low_price_rows = _rows(20.0, 0.18)
    spy_index = {row["date"]: idx for idx, row in enumerate(spy_rows)}

    high_feature = build_broad_market_feature(
        ticker="WIN",
        rows=high_price_rows,
        idx=60,
        spy_rows=spy_rows,
        spy_index=spy_index,
    )
    low_feature = build_broad_market_feature(
        ticker="LOW",
        rows=low_price_rows,
        idx=60,
        spy_rows=spy_rows,
        spy_index=spy_index,
    )

    assert high_feature is not None
    assert high_feature["close"] >= 40.0
    assert candidate_passes_profile(high_feature)
    assert low_feature is not None
    assert low_feature["close"] < 40.0
    assert not candidate_passes_profile(low_feature)


def test_candidate_builder_excludes_tradeable_and_title_noise():
    spy_rows = _rows(100.0, 0.02)
    win_rows = _rows(50.0, 0.35)
    etf_rows = _rows(55.0, 0.30)
    ohlcv = {"SPY": spy_rows, "WIN": win_rows, "ETFZ": etf_rows, "CORE": win_rows}

    candidates = build_broad_market_paper_candidates(
        as_of=spy_rows[60]["date"],
        ohlcv_by_ticker=ohlcv,
        candidate_tickers=["WIN", "ETFZ", "CORE"],
        ticker_metadata={"ETFZ": {"title": "Example Growth ETF"}},
        current_tradeable_universe={"CORE"},
    )

    assert [row["ticker"] for row in candidates] == ["WIN"]
    assert candidates[0]["trade_enabled"] is False
    assert candidates[0]["intended_notional"] == 7500.0


def test_snapshot_adds_pending_and_fills_next_session_without_orders():
    spy_rows = _rows(100.0, 0.02)
    win_rows = _rows(50.0, 0.35)
    ohlcv = {"SPY": spy_rows, "WIN": win_rows}

    first = build_broad_market_paper_sleeve_snapshot(
        as_of=spy_rows[60]["date"],
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["WIN"],
        state=empty_broad_market_paper_state(),
        persist=False,
    )
    assert first["candidate_count"] == 1
    assert first["new_pending_count"] == 1
    assert first["pending_count"] == 1
    assert first["production_impact"]["alters_orders"] is False

    state = empty_broad_market_paper_state()
    state["pending_entries"] = first["pending_entries"]
    second = build_broad_market_paper_sleeve_snapshot(
        as_of=spy_rows[61]["date"],
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["WIN"],
        state=state,
        persist=False,
    )
    assert second["filled_count"] == 1
    assert second["open_position_count"] == 1
    assert second["trade_enabled"] is False
