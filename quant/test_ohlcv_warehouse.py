from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, os.path.dirname(__file__))

from backtester import BacktestEngine  # noqa: E402
from ohlcv_warehouse import (  # noqa: E402
    load_warehouse_snapshot_ohlcv_frames,
    load_warehouse_ohlcv_frames,
    seed_warehouse_snapshot_versions,
    seed_warehouse_from_snapshots,
    upsert_ohlcv_frames,
)


def _write_snapshot(path: Path) -> None:
    payload = {
        "metadata": {"tickers": ["AAA", "IWM"]},
        "ohlcv": {
            "AAA": [
                {
                    "Date": "2025-01-02",
                    "Open": 10.0,
                    "High": 11.0,
                    "Low": 9.5,
                    "Close": 10.5,
                    "Volume": 1000,
                },
                {
                    "Date": "2025-01-03",
                    "Open": 10.5,
                    "High": 11.5,
                    "Low": 10.0,
                    "Close": 11.0,
                    "Volume": 1100,
                },
            ],
            "IWM": [
                {
                    "Date": "2025-01-02",
                    "Open": 200.0,
                    "High": 201.0,
                    "Low": 199.0,
                    "Close": 200.5,
                    "Volume": 2000,
                }
            ],
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_snapshot_with_close(path: Path, close: float, tickers=None) -> None:
    tickers = tickers or ["AAA"]
    payload = {
        "metadata": {"tickers": tickers},
        "ohlcv": {
            ticker: [
                {
                    "Date": "2025-01-02",
                    "Open": 10.0,
                    "High": 11.0,
                    "Low": 9.0,
                    "Close": close,
                    "Volume": 1000,
                }
            ]
            for ticker in tickers
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_seed_warehouse_from_snapshots_inserts_reference_rows(tmp_path):
    db_path = tmp_path / "warehouse.sqlite"
    snapshot_path = tmp_path / "ohlcv_snapshot.json"
    _write_snapshot(snapshot_path)

    summary = seed_warehouse_from_snapshots(db_path, [snapshot_path])

    assert summary["inserted"] == 3
    assert summary["updated"] == 0
    with sqlite3.connect(db_path) as con:
        tickers = {
            row[0]
            for row in con.execute("SELECT DISTINCT ticker FROM ohlcv ORDER BY ticker")
        }
        iwm_status = con.execute(
            "SELECT status, provider FROM fetch_status WHERE ticker = 'IWM'"
        ).fetchone()
    assert tickers == {"AAA", "IWM"}
    assert iwm_status == ("seeded_local_reference", "local_snapshot_seed")


def test_seed_warehouse_from_snapshots_updates_existing_values(tmp_path):
    db_path = tmp_path / "warehouse.sqlite"
    snapshot_path = tmp_path / "ohlcv_snapshot.json"
    _write_snapshot(snapshot_path)
    seed_warehouse_from_snapshots(db_path, [snapshot_path])

    with sqlite3.connect(db_path) as con:
        con.execute(
            "UPDATE ohlcv SET close = 99.0 WHERE ticker = 'AAA' AND date = '2025-01-02'"
        )
        con.commit()

    summary = seed_warehouse_from_snapshots(db_path, [snapshot_path])

    assert summary["inserted"] == 0
    assert summary["updated"] == 1
    with sqlite3.connect(db_path) as con:
        close = con.execute(
            "SELECT close FROM ohlcv WHERE ticker = 'AAA' AND date = '2025-01-02'"
        ).fetchone()[0]
    assert close == 10.5


def test_load_warehouse_ohlcv_frames_returns_backtester_shape(tmp_path):
    db_path = tmp_path / "warehouse.sqlite"
    snapshot_path = tmp_path / "ohlcv_snapshot.json"
    _write_snapshot(snapshot_path)
    seed_warehouse_from_snapshots(db_path, [snapshot_path])

    frames = load_warehouse_ohlcv_frames(
        db_path,
        ["AAA", "IWM", "MISSING"],
        "2025-01-01",
        "2025-01-10",
    )

    assert sorted(frames) == ["AAA", "IWM"]
    assert list(frames["AAA"].columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert float(frames["AAA"].loc["2025-01-02", "Close"]) == 10.5


def test_seed_snapshot_versions_preserves_overlapping_sources(tmp_path):
    db_path = tmp_path / "warehouse.sqlite"
    old_snapshot = tmp_path / "old_snapshot.json"
    new_snapshot = tmp_path / "new_snapshot.json"
    _write_snapshot_with_close(old_snapshot, 10.5)
    _write_snapshot_with_close(new_snapshot, 99.0)

    summary = seed_warehouse_snapshot_versions(
        db_path,
        [old_snapshot, new_snapshot],
    )

    assert summary["inserted"] == 2
    old_frames = load_warehouse_snapshot_ohlcv_frames(
        db_path,
        old_snapshot,
        ["AAA"],
        "2025-01-01",
        "2025-01-10",
    )
    new_frames = load_warehouse_snapshot_ohlcv_frames(
        db_path,
        new_snapshot,
        ["AAA"],
        "2025-01-01",
        "2025-01-10",
    )
    assert float(old_frames["AAA"].loc["2025-01-02", "Close"]) == 10.5
    assert float(new_frames["AAA"].loc["2025-01-02", "Close"]) == 99.0


def test_upsert_ohlcv_frames_inserts_without_overwriting_existing(tmp_path):
    db_path = tmp_path / "warehouse.sqlite"
    snapshot_path = tmp_path / "ohlcv_snapshot.json"
    _write_snapshot(snapshot_path)
    seed_warehouse_from_snapshots(db_path, [snapshot_path])

    frame = load_warehouse_ohlcv_frames(
        db_path,
        ["AAA"],
        "2025-01-01",
        "2025-01-10",
    )["AAA"].copy()
    frame.loc["2025-01-02", "Close"] = 99.0
    frame.loc["2025-01-06"] = {
        "Open": 12.0,
        "High": 13.0,
        "Low": 11.5,
        "Close": 12.5,
        "Volume": 1200,
    }

    summary = upsert_ohlcv_frames(
        db_path,
        {"AAA": frame},
        source="test_daily_run",
    )

    assert summary["inserted"] == 1
    assert summary["updated"] == 0
    assert summary["skipped_existing"] == 2
    with sqlite3.connect(db_path) as con:
        old_close = con.execute(
            "SELECT close FROM ohlcv WHERE ticker = 'AAA' AND date = '2025-01-02'"
        ).fetchone()[0]
        new_close = con.execute(
            "SELECT close FROM ohlcv WHERE ticker = 'AAA' AND date = '2025-01-06'"
        ).fetchone()[0]
        status = con.execute(
            "SELECT status, provider FROM fetch_status WHERE ticker = 'AAA'"
        ).fetchone()
    assert old_close == 10.5
    assert new_close == 12.5
    assert status == ("ok", "yfinance")


def test_upsert_ohlcv_frames_can_update_existing_when_explicit(tmp_path):
    db_path = tmp_path / "warehouse.sqlite"
    snapshot_path = tmp_path / "ohlcv_snapshot.json"
    _write_snapshot(snapshot_path)
    seed_warehouse_from_snapshots(db_path, [snapshot_path])

    frame = load_warehouse_ohlcv_frames(
        db_path,
        ["AAA"],
        "2025-01-01",
        "2025-01-10",
    )["AAA"].copy()
    frame.loc["2025-01-02", "Close"] = 99.0

    summary = upsert_ohlcv_frames(
        db_path,
        {"AAA": frame},
        source="test_refresh",
        update_existing=True,
    )

    assert summary["inserted"] == 0
    assert summary["updated"] == 1
    with sqlite3.connect(db_path) as con:
        close = con.execute(
            "SELECT close FROM ohlcv WHERE ticker = 'AAA' AND date = '2025-01-02'"
        ).fetchone()[0]
    assert close == 99.0


def test_backtester_download_data_can_use_warehouse(tmp_path):
    db_path = tmp_path / "warehouse.sqlite"
    snapshot_path = tmp_path / "ohlcv_snapshot.json"
    payload = {
        "metadata": {"tickers": ["AAA", "SPY", "QQQ"]},
        "ohlcv": {
            ticker: [
                {
                    "Date": "2025-01-02",
                    "Open": 10.0,
                    "High": 11.0,
                    "Low": 9.0,
                    "Close": 10.5,
                    "Volume": 1000,
                }
            ]
            for ticker in ["AAA", "SPY", "QQQ"]
        },
    }
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
    seed_warehouse_from_snapshots(db_path, [snapshot_path])
    engine = BacktestEngine(
        ["AAA"],
        start="2025-01-02",
        end="2025-01-02",
        ohlcv_warehouse_path=str(db_path),
    )

    frames = engine._download_data()

    assert sorted(frames) == ["AAA", "QQQ", "SPY"]


def test_backtester_download_data_can_use_warehouse_snapshot_source(tmp_path):
    db_path = tmp_path / "warehouse.sqlite"
    old_snapshot = tmp_path / "old_snapshot.json"
    new_snapshot = tmp_path / "new_snapshot.json"
    _write_snapshot_with_close(old_snapshot, 10.5, tickers=["AAA", "SPY", "QQQ"])
    _write_snapshot_with_close(new_snapshot, 99.0, tickers=["AAA", "SPY", "QQQ"])
    seed_warehouse_snapshot_versions(db_path, [old_snapshot, new_snapshot])
    engine = BacktestEngine(
        ["AAA"],
        start="2025-01-02",
        end="2025-01-02",
        ohlcv_warehouse_path=str(db_path),
        ohlcv_warehouse_snapshot_source=str(old_snapshot),
    )

    frames = engine._download_data()

    assert sorted(frames) == ["AAA", "QQQ", "SPY"]
    assert float(frames["AAA"].loc["2025-01-02", "Close"]) == 10.5
