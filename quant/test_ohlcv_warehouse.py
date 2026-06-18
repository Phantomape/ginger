from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd


sys.path.insert(0, os.path.dirname(__file__))

from backtester import BacktestEngine  # noqa: E402
from ohlcv_warehouse import (  # noqa: E402
    hot_path_for,
    hot_status,
    load_warehouse_snapshot_ohlcv_frames,
    load_warehouse_ohlcv_frames,
    merge_hot_into_cold,
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


def test_backtester_resolves_absolute_legacy_snapshot_path():
    repo_root = Path(__file__).resolve().parents[1]
    legacy = repo_root / "data" / "ohlcv_snapshot_20241002_20250422.json"
    expected = (
        repo_root / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json"
    )

    assert expected.exists()
    engine = BacktestEngine([], start="2025-01-02", end="2025-01-02")

    assert Path(engine._resolve_snapshot_path(str(legacy))) == expected


def _seed_cold(db_path: Path) -> None:
    _write_snapshot(db_path.with_suffix(".snap.json"))
    seed_warehouse_from_snapshots(db_path, [db_path.with_suffix(".snap.json")])


def test_hot_path_for_is_sibling_of_cold(tmp_path):
    cold = tmp_path / "warehouse_main.sqlite"
    assert hot_path_for(cold) == tmp_path / "warehouse_main_hot.sqlite"


def test_load_overlays_hot_tier_with_hot_winning(tmp_path):
    cold = tmp_path / "warehouse_main.sqlite"
    _seed_cold(cold)  # AAA 01-02 (10.5), 01-03 (11.0)

    # Hot tier: a corrected 01-03 close + a brand-new 01-06 bar.
    hot_frame = load_warehouse_ohlcv_frames(cold, ["AAA"], "2025-01-01", "2025-01-10")[
        "AAA"
    ].copy()
    hot_frame.loc["2025-01-03", "Close"] = 99.0
    hot_frame.loc["2025-01-06"] = {
        "Open": 12.0,
        "High": 13.0,
        "Low": 11.5,
        "Close": 12.5,
        "Volume": 1200,
    }
    upsert_ohlcv_frames(hot_path_for(cold), {"AAA": hot_frame}, source="hot")

    # Readers pass the cold path; the hot tier overlays transparently, winning
    # on the (AAA, 2025-01-03) conflict and adding the new 2025-01-06 bar.
    frames = load_warehouse_ohlcv_frames(cold, ["AAA"], "2025-01-01", "2025-01-10")
    closes = frames["AAA"]["Close"].to_dict()
    assert float(closes[pd.Timestamp("2025-01-02")]) == 10.5
    assert float(closes[pd.Timestamp("2025-01-03")]) == 99.0
    assert float(closes[pd.Timestamp("2025-01-06")]) == 12.5


def test_load_without_hot_sibling_is_unchanged(tmp_path):
    cold = tmp_path / "warehouse_main.sqlite"
    _seed_cold(cold)
    assert not hot_path_for(cold).exists()
    frames = load_warehouse_ohlcv_frames(cold, ["AAA"], "2025-01-01", "2025-01-10")
    assert float(frames["AAA"].loc["2025-01-03", "Close"]) == 11.0


def test_merge_hot_folds_new_rows_and_resets_hot(tmp_path):
    cold = tmp_path / "warehouse_main.sqlite"
    _seed_cold(cold)  # AAA 01-02, 01-03

    hot_frame = load_warehouse_ohlcv_frames(cold, ["AAA"], "2025-01-01", "2025-01-10")[
        "AAA"
    ].copy()
    hot_frame.loc["2025-01-03", "Close"] = 99.0  # overlap (corrected)
    hot_frame.loc["2025-01-06"] = {
        "Open": 12.0,
        "High": 13.0,
        "Low": 11.5,
        "Close": 12.5,
        "Volume": 1200,
    }
    upsert_ohlcv_frames(hot_path_for(cold), {"AAA": hot_frame}, source="hot")

    summary = merge_hot_into_cold(cold)

    # Only the genuinely new 01-06 bar inserts; the two overlapping deterministic
    # cold rows (01-02, 01-03) are preserved (INSERT OR IGNORE), matching
    # update_existing=False.
    assert summary["status"] == "merged"
    assert summary["inserted"] == 1
    assert summary["skipped_existing"] == 2
    with sqlite3.connect(cold) as con:
        kept = con.execute(
            "SELECT close FROM ohlcv WHERE ticker = 'AAA' AND date = '2025-01-03'"
        ).fetchone()[0]
        added = con.execute(
            "SELECT close FROM ohlcv WHERE ticker = 'AAA' AND date = '2025-01-06'"
        ).fetchone()[0]
    assert kept == 11.0
    assert added == 12.5

    # Hot is emptied so the committed blob shrinks back for the next window.
    assert hot_status(cold)["row_count"] == 0


def test_merge_hot_no_hot_is_noop(tmp_path):
    cold = tmp_path / "warehouse_main.sqlite"
    _seed_cold(cold)
    summary = merge_hot_into_cold(cold)
    assert summary["status"] == "no_hot"
    assert summary["inserted"] == 0
