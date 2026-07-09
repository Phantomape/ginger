"""Tests for the chop forward observer wiring (exp-20260708-030)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from chop_forward_observer import (
    ENTRY_WINDOW_TRADING_DAYS,
    persist_chop_forward_observations,
)


def _dates(n: int) -> list[str]:
    d0 = date(2025, 1, 1)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def _frame(prices: list[float], dates: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {"Open": prices, "High": prices, "Low": prices, "Close": prices},
        index=pd.to_datetime(dates),
    )


def test_skips_gracefully_without_spy_history(tmp_path):
    result = persist_chop_forward_observations({}, as_of="2026-07-08", data_dir=tmp_path)
    assert result["status"] == "skipped_insufficient_spy_history"
    assert not (tmp_path / "paper_sleeves" / "chop_forward" / "rows.jsonl").exists()


def test_writes_ledger_and_is_idempotent(tmp_path):
    n = 320
    dates = _dates(n)
    spy = _frame([500.0 + 0.05 * i for i in range(n)], dates)
    acme = _frame([100.0 + 0.1 * i for i in range(n)], dates)
    frames = {"SPY": spy, "QQQ": spy, "ACME": acme}

    first = persist_chop_forward_observations(frames, as_of=dates[-1], data_dir=tmp_path)
    assert first["status"] == "ok"
    assert first["window_end"] == dates[-1]
    # steady uptrend -> risk_on; the observer still writes a summary + ledger dir
    summary_path = tmp_path / "paper_sleeves" / "chop_forward" / "summary.json"
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["rows_total"] == first["rows_total"]
    assert payload["production_impact"]["trade_enabled"] is False

    second = persist_chop_forward_observations(frames, as_of=dates[-1], data_dir=tmp_path)
    assert second["rows_total"] == first["rows_total"]  # idempotent re-run

    rows_path = tmp_path / "paper_sleeves" / "chop_forward" / "rows.jsonl"
    if rows_path.exists():
        keys = [
            (r["bundle"], r.get("pair") or r.get("ticker"), r["signal_date"])
            for r in map(json.loads, rows_path.read_text(encoding="utf-8").splitlines())
        ]
        assert len(keys) == len(set(keys))  # upsert key uniqueness


def test_closed_rows_never_regress_to_open(tmp_path):
    """A closed row must survive a later run that re-derives it as open."""
    ledger = tmp_path / "paper_sleeves" / "chop_forward"
    ledger.mkdir(parents=True)
    closed_row = {
        "bundle": "chop_mean_reversion_v1",
        "ticker": "ACME",
        "signal_date": "2025-06-01",
        "exit_reason": "close_above_sma5",
        "row_status": "closed",
        "pnl_usd": 42.0,
    }
    (ledger / "rows.jsonl").write_text(
        json.dumps(closed_row) + "\n", encoding="utf-8"
    )
    n = 320
    dates = _dates(n)
    spy = _frame([500.0 + 0.05 * i for i in range(n)], dates)
    persist_chop_forward_observations({"SPY": spy, "QQQ": spy}, as_of=dates[-1], data_dir=tmp_path)
    rows = [
        json.loads(line)
        for line in (ledger / "rows.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    kept = [r for r in rows if r.get("ticker") == "ACME" and r["signal_date"] == "2025-06-01"]
    assert kept and kept[0]["row_status"] == "closed" and kept[0]["pnl_usd"] == 42.0


def test_run_py_wiring_present():
    source = (Path(__file__).resolve().parent / "run.py").read_text(encoding="utf-8")
    assert "persist_chop_forward_observations" in source
    assert "Chop forward observer unavailable" in source  # failure-tolerant guard


def test_entry_window_covers_max_hold():
    from chop_mean_reversion_sleeve import MAX_HOLD_TRADING_DAYS as MR_HOLD
    from chop_pairs_spread_sleeve import MAX_HOLD_TRADING_DAYS as PAIRS_HOLD

    assert ENTRY_WINDOW_TRADING_DAYS > max(MR_HOLD, PAIRS_HOLD) + 20
