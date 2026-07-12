"""Tests for the iBorrowDesk borrow-economics archive (exp-20260712-013)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import iborrowdesk_data_source as ibd


@pytest.fixture()
def isolated_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(ibd, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(ibd, "HISTORY_DIR", tmp_path / "history")
    monkeypatch.setattr(ibd, "FETCH_STATE_PATH", tmp_path / "fetch_state.json")
    return tmp_path


def test_merge_is_append_only_by_date(isolated_archive):
    first = ibd.merge_daily_rows(
        "test", [{"date": "2026-07-01", "fee": 0.5, "available": 100000}]
    )
    assert first == {"added": 1, "total": 1}
    # A later fetch reporting a different value for the same date must NOT
    # rewrite the archived PIT row; only genuinely new dates are added.
    second = ibd.merge_daily_rows(
        "test",
        [
            {"date": "2026-07-01", "fee": 9.9, "available": 1},
            {"date": "2026-07-02", "fee": 0.75, "available": 90000},
        ],
    )
    assert second == {"added": 1, "total": 2}
    rows = ibd.load_history("test")["rows"]
    assert rows["2026-07-01"]["fee"] == 0.5
    assert rows["2026-07-02"]["fee"] == 0.75
    assert "archived_at" in rows["2026-07-01"]


def test_merge_skips_malformed_dates_and_non_numeric_fields(isolated_archive):
    result = ibd.merge_daily_rows(
        "test",
        [
            {"date": "bad", "fee": 1.0},
            {"date": "2026-07-03", "fee": None, "available": "n/a", "rebate": 4.0},
        ],
    )
    assert result == {"added": 1, "total": 1}
    row = ibd.load_history("test")["rows"]["2026-07-03"]
    assert "fee" not in row and "available" not in row
    assert row["rebate"] == 4.0


def test_refresh_rotates_stalest_first_and_resumes(isolated_archive, monkeypatch):
    calls: list[str] = []

    def fake_fetch(symbol, **kwargs):
        calls.append(symbol)
        return {"daily": [{"date": "2026-07-10", "fee": 0.25, "available": 10000}]}

    monkeypatch.setattr(ibd, "fetch_ticker_payload", fake_fetch)
    summary = ibd.refresh_archive(["AAA", "BBB", "CCC"], max_fetches=2, sleep_s=0.0)
    assert summary["attempted"] == 2
    assert summary["succeeded"] == 2
    # Second pass with min_age_days>0 must pick the not-yet-fetched ticker.
    summary2 = ibd.refresh_archive(
        ["AAA", "BBB", "CCC"], max_fetches=2, min_age_days=0.5, sleep_s=0.0
    )
    assert summary2["attempted"] == 1
    assert set(calls) == {"AAA", "BBB", "CCC"}
    state = json.loads(ibd.FETCH_STATE_PATH.read_text(encoding="utf-8"))
    assert all(meta["status"] == "ok" for meta in state["tickers"].values())


def test_refresh_aborts_early_on_consecutive_failures(isolated_archive, monkeypatch):
    def fail_fetch(symbol, **kwargs):
        raise TimeoutError("host down")

    monkeypatch.setattr(ibd, "fetch_ticker_payload", fail_fetch)
    tickers = [f"T{i}" for i in range(10)]
    summary = ibd.refresh_archive(
        tickers, max_fetches=10, sleep_s=0.0, max_consecutive_failures=3
    )
    assert summary["aborted_early"] is True
    assert summary["attempted"] == 3
    assert summary["succeeded"] == 0
