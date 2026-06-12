from __future__ import annotations

import pandas as pd

from quant.ohlcv_warehouse import upsert_ohlcv_frames
from quant.ohlcv_warehouse_refresh import (
    plan_refresh,
    refresh_warehouse_ohlcv,
    warehouse_last_dates,
)

AS_OF = "2026-06-10"


def _frame(end: str, days: int) -> pd.DataFrame:
    index = pd.bdate_range(end=end, periods=days)
    base = pd.Series(range(1, days + 1), index=index, dtype=float)
    return pd.DataFrame(
        {
            "Open": base + 10.0,
            "High": base + 11.0,
            "Low": base + 9.0,
            "Close": base + 10.5,
            "Volume": base * 1000.0,
        },
        index=index,
    )


def _seed(db_path, frames):
    upsert_ohlcv_frames(db_path, frames, source="test_seed")


def test_plan_buckets_stale_new_and_fresh_tickers(tmp_path) -> None:
    db = tmp_path / "warehouse.sqlite"
    _seed(
        db,
        {
            "STALE": _frame("2026-04-24", 30),
            "FRESH": _frame(AS_OF, 30),
        },
    )

    plan = plan_refresh(db_path=db, tickers=["STALE", "FRESH", "BRANDNEW"], as_of=AS_OF)

    assert plan["fresh_count"] == 1
    assert plan["stale_count"] == 2
    # 47-day gap + 5 pad days lands in the 90-day bucket; unseen tickers get max lookback.
    assert plan["buckets"]["90"] == ["STALE"]
    assert plan["buckets"]["420"] == ["BRANDNEW"]


def test_refresh_inserts_missing_days_and_is_idempotent(tmp_path) -> None:
    db = tmp_path / "warehouse.sqlite"
    _seed(db, {"STALE": _frame("2026-04-24", 30)})

    calls: list[tuple[tuple[str, ...], int]] = []

    def fake_fetch(tickers: list[str], lookback_days: int) -> dict[str, pd.DataFrame]:
        calls.append((tuple(tickers), lookback_days))
        return {ticker: _frame(AS_OF, 60) for ticker in tickers}

    summary = refresh_warehouse_ohlcv(
        db_path=db,
        tickers=["STALE", "BRANDNEW"],
        as_of=AS_OF,
        fetch_many=fake_fetch,
    )

    assert summary["status"] == "completed"
    assert summary["fetched_ticker_count"] == 2
    assert summary["inserted"] > 0
    assert summary["errors"] == []
    assert len(calls) == 2  # one 90-day bucket chunk + one 420-day bucket chunk
    last = warehouse_last_dates(db, ["STALE", "BRANDNEW"])
    assert last["STALE"] == AS_OF
    assert last["BRANDNEW"] == AS_OF

    # Second run: everything fresh, no vendor calls, nothing inserted.
    calls.clear()
    again = refresh_warehouse_ohlcv(
        db_path=db,
        tickers=["STALE", "BRANDNEW"],
        as_of=AS_OF,
        fetch_many=fake_fetch,
    )
    assert calls == []
    assert again["fresh_count"] == 2
    assert again["inserted"] == 0


def test_refresh_dry_run_fetches_nothing(tmp_path) -> None:
    db = tmp_path / "warehouse.sqlite"
    _seed(db, {"STALE": _frame("2026-04-24", 30)})

    def exploding_fetch(tickers: list[str], lookback_days: int) -> dict[str, pd.DataFrame]:
        raise AssertionError("dry run must not fetch")

    summary = refresh_warehouse_ohlcv(
        db_path=db,
        tickers=["STALE"],
        as_of=AS_OF,
        fetch_many=exploding_fetch,
        dry_run=True,
    )
    assert summary["status"] == "dry_run"
    assert summary["stale_count"] == 1
    assert summary["inserted"] == 0


def test_refresh_records_fetch_errors_per_chunk(tmp_path) -> None:
    db = tmp_path / "warehouse.sqlite"
    _seed(db, {"STALE": _frame("2026-04-24", 30)})

    def failing_fetch(tickers: list[str], lookback_days: int) -> dict[str, pd.DataFrame]:
        raise RuntimeError("vendor down")

    summary = refresh_warehouse_ohlcv(
        db_path=db,
        tickers=["STALE"],
        as_of=AS_OF,
        fetch_many=failing_fetch,
    )
    assert summary["status"] == "partial_failed"
    assert summary["errors"] and "vendor down" in summary["errors"][0]["error"]
    assert summary["inserted"] == 0
