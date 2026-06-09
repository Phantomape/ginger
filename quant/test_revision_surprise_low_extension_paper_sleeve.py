from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from quant import revision_surprise_low_extension_paper_sleeve as sleeve


def _dates(count: int) -> list[str]:
    start = date(2026, 1, 1)
    return [(start + timedelta(days=idx)).isoformat() for idx in range(count)]


def _rows(
    dates: list[str],
    *,
    signal_idx: int,
    signal_close: float,
    signal_volume: float = 1_400_000.0,
    exit_close: float = 122.0,
) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for idx, day in enumerate(dates):
        close = 100.0 + idx * 0.05
        high = close + 0.5
        low = close - 0.5
        open_price = close - 0.1
        volume = 1_000_000.0
        if idx == signal_idx:
            close = signal_close
            high = signal_close + 1.0
            low = signal_close - 9.0
            open_price = signal_close - 2.0
            volume = signal_volume
        if idx == signal_idx + 1:
            open_price = signal_close + 1.0
            close = signal_close + 1.5
            high = close + 0.5
            low = open_price - 0.5
        if idx == signal_idx + sleeve.DEFAULT_CONFIG["hold_days"]:
            close = exit_close
            high = close + 0.5
            low = close - 0.5
            open_price = close - 0.2
        rows.append(
            {
                "date": day,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
    return rows


def _spy_rows(dates: list[str]) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for idx, day in enumerate(dates):
        close = 400.0 + idx * 0.1
        rows.append(
            {
                "date": day,
                "open": close,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": 10_000_000.0,
            }
        )
    return rows


def _write_earnings_snapshots(
    snapshot_dir: Path,
    dates: list[str],
    *,
    signal_idx: int,
    tickers: list[str],
) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    prior_idx = signal_idx - sleeve.DEFAULT_CONFIG["revision_lookback_trading_days"]
    for idx, day in enumerate(dates):
        tag = day.replace("-", "")
        earnings = {}
        for ticker in tickers:
            estimate = 1.0
            if idx == signal_idx:
                estimate = 1.08 if ticker == "HOT" else 1.05
            if idx == prior_idx:
                estimate = 1.0
            earnings[ticker] = {
                "eps_estimate": estimate,
                "days_to_earnings": 30,
                "avg_historical_surprise_pct": 3.5,
                "historical_surprise_pct": [1.0, 2.0, 3.0, 4.0],
            }
        (snapshot_dir / f"earnings_snapshot_{tag}.json").write_text(
            json.dumps({"earnings": earnings}, sort_keys=True),
            encoding="utf-8",
        )


def test_snapshot_creates_pending_without_future_bars(tmp_path: Path) -> None:
    dates = _dates(38)
    signal_idx = 25
    snapshot_dir = tmp_path / "earnings"
    _write_earnings_snapshots(snapshot_dir, dates[: signal_idx + 1], signal_idx=signal_idx, tickers=["PASS"])
    ohlcv = {
        "SPY": _spy_rows(dates[: signal_idx + 1]),
        "PASS": _rows(dates[: signal_idx + 1], signal_idx=signal_idx, signal_close=115.0),
    }

    snapshot = sleeve.build_revision_surprise_low_extension_snapshot(
        as_of=dates[signal_idx],
        ohlcv_by_ticker=ohlcv,
        earnings_snapshot_dir=snapshot_dir,
        state=sleeve.empty_revision_surprise_low_extension_state(),
        persist=False,
    )

    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["alters_orders"] is False
    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["new_pending_entries"][0]["ticker"] == "PASS"
    assert "entry_date" not in snapshot["new_pending_entries"][0]
    assert snapshot["closed_count_today"] == 0


def test_historical_replay_and_snapshot_share_candidate(tmp_path: Path) -> None:
    dates = _dates(42)
    signal_idx = 25
    snapshot_dir = tmp_path / "earnings"
    _write_earnings_snapshots(snapshot_dir, dates, signal_idx=signal_idx, tickers=["PASS"])
    full_ohlcv = {
        "SPY": _spy_rows(dates),
        "PASS": _rows(dates, signal_idx=signal_idx, signal_close=115.0, exit_close=124.0),
    }
    snapshot_ohlcv = {
        ticker: rows[: signal_idx + 1] for ticker, rows in full_ohlcv.items()
    }

    snapshot = sleeve.build_revision_surprise_low_extension_snapshot(
        as_of=dates[signal_idx],
        ohlcv_by_ticker=snapshot_ohlcv,
        earnings_snapshot_dir=snapshot_dir,
        state=sleeve.empty_revision_surprise_low_extension_state(),
        persist=False,
    )
    trades, audit = sleeve.build_revision_surprise_low_extension_historical_trades(
        ohlcv_by_ticker=full_ohlcv,
        core_entries_by_date={},
        windows={"test": {"start": dates[signal_idx], "end": dates[signal_idx]}},
        earnings_snapshot_dir=snapshot_dir,
    )

    assert audit["selected_by_window"]["test"] == 1
    assert len(trades) == 1
    assert trades[0]["ticker"] == snapshot["candidate"]["ticker"] == "PASS"
    assert trades[0]["signal_date"] == snapshot["candidate"]["signal_date"] == dates[signal_idx]
    assert trades[0]["entry_date"] == dates[signal_idx + 1]
    assert trades[0]["exit_date"] == dates[signal_idx + sleeve.DEFAULT_CONFIG["hold_days"]]
    assert trades[0]["pnl"] > 0


def test_overextended_top1_blocks_without_backup_substitution(tmp_path: Path) -> None:
    dates = _dates(42)
    signal_idx = 25
    snapshot_dir = tmp_path / "earnings"
    _write_earnings_snapshots(snapshot_dir, dates, signal_idx=signal_idx, tickers=["HOT", "PASS"])
    ohlcv = {
        "SPY": _spy_rows(dates),
        "HOT": _rows(dates, signal_idx=signal_idx, signal_close=170.0, exit_close=150.0),
        "PASS": _rows(dates, signal_idx=signal_idx, signal_close=115.0, exit_close=124.0),
    }

    candidates, _, scan = sleeve.build_revision_surprise_low_extension_candidate_rows(
        ohlcv_by_ticker=ohlcv,
        dates=[dates[signal_idx]],
        core_entries_by_date={},
        earnings_snapshot_dir=snapshot_dir,
        require_future_bars=True,
    )
    selected, rejected = sleeve.select_revision_surprise_low_extension_signal_rows(
        candidates=candidates,
    )

    assert scan["raw_candidate_count"] == 2
    assert selected == []
    assert any(row["ticker"] == "HOT" and row["filter_reason"] == "ret20_excess_spy_above_tail_cap" for row in rejected)
    assert any(row["ticker"] == "PASS" and row["filter_reason"] == "daily_top1_limit" for row in rejected)
