"""Tests for the live-vs-model drift reconciliation surface (exp-20260706-019)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from fill_model import SLIPPAGE_BPS_ENTRY, apply_slippage  # noqa: E402
import live_drift_reconciliation as ldr  # noqa: E402
from live_drift_reconciliation import (  # noqa: E402
    ALERT_CONSECUTIVE_SESSIONS,
    build_live_drift_reconciliation,
    evaluate_drift_alert,
    reconcile_position,
    strategy_bucket,
)


def _bars():
    return [
        {"date": "2026-06-01", "open": 100.0, "close": 101.0},
        {"date": "2026-06-02", "open": 101.0, "close": 102.0},
        {"date": "2026-06-03", "open": 102.0, "close": 104.0},
    ]


def _position(**overrides):
    base = {
        "ticker": "NVDA",
        "direction": "long",
        "shares": 10.0,
        "avg_cost": 100.30,
        "entry_date": "2026-06-01",
        "market_val": 1040.0,
        "unrealized_pl": 37.0,
        "opened_by_strategy": "trend_long",
        "sleeve": "core",
        "position_id": 111,
    }
    base.update(overrides)
    return base


def _write_warehouse(path: Path, rows: list[tuple[str, str, float, float]]) -> None:
    con = sqlite3.connect(path)
    try:
        con.execute("create table ohlcv (ticker text, date text, open real, close real)")
        con.executemany("insert into ohlcv values (?, ?, ?, ?)", rows)
        con.commit()
    finally:
        con.close()


def test_strategy_bucket_classification():
    assert strategy_bucket(_position()) == "core"
    assert strategy_bucket(_position(opened_by_strategy="legacy", sleeve="discretionary")) == (
        "discretionary_legacy"
    )
    assert strategy_bucket(_position(sleeve="form4", opened_by_strategy="form4_sleeve")) == "sleeve"


def test_default_warehouse_paths_prefer_hot_current_surface():
    assert ldr.WAREHOUSE_PATHS[0].name == "warehouse_main_hot.sqlite"


def test_bars_from_warehouse_prefers_hot_and_falls_back_on_empty(tmp_path, monkeypatch):
    hot = tmp_path / "warehouse_main_hot.sqlite"
    stale = tmp_path / "warehouse_main.sqlite"
    _write_warehouse(stale, [("HOOD", "2026-06-12", 100.0, 101.0)])
    _write_warehouse(hot, [("HOOD", "2026-06-18", 107.0, 108.0)])

    monkeypatch.setattr(ldr, "WAREHOUSE_PATHS", (hot, stale))
    rows = ldr._bars_from_warehouse("HOOD")
    assert rows[-1]["date"] == "2026-06-18"

    empty_hot = tmp_path / "empty_hot.sqlite"
    _write_warehouse(empty_hot, [])
    monkeypatch.setattr(ldr, "WAREHOUSE_PATHS", (empty_hot, stale))
    rows = ldr._bars_from_warehouse("HOOD")
    assert rows[-1]["date"] == "2026-06-12"


def test_reconcile_position_arithmetic():
    row = reconcile_position(_position(), _bars(), "2026-06-03")
    assert row["reconcilable"] is True

    modeled_entry = apply_slippage(100.0, SLIPPAGE_BPS_ENTRY, "buy")
    assert abs(row["modeled_entry_price"] - round(modeled_entry, 4)) < 1e-9
    assert abs(row["fill_drift_pct"] - (100.30 / modeled_entry - 1.0)) < 1e-6
    # realized mark = 1040/10 = 104.0 vs avg_cost 100.30
    assert abs(row["realized_return_pct"] - (104.0 / 100.30 - 1.0)) < 1e-6
    assert abs(row["modeled_return_pct"] - (104.0 / modeled_entry - 1.0)) < 1e-6
    assert abs(
        row["trajectory_drift_pct"]
        - (row["realized_return_pct"] - row["modeled_return_pct"])
    ) < 1e-6


def test_reconcile_position_entry_on_non_session_uses_next_bar():
    row = reconcile_position(_position(entry_date="2026-05-31"), _bars(), "2026-06-03")
    assert row["reconcilable"] is True
    assert abs(
        row["modeled_entry_price"] - round(apply_slippage(100.0, SLIPPAGE_BPS_ENTRY, "buy"), 4)
    ) < 1e-9


def test_reconcile_position_fail_safe_reasons():
    assert reconcile_position(_position(entry_date=None), _bars(), "2026-06-03")["reason"] == (
        "missing_entry_date"
    )
    assert reconcile_position(_position(avg_cost=None), _bars(), "2026-06-03")["reason"] == (
        "missing_cost_basis"
    )
    assert reconcile_position(_position(entry_date="2026-07-01"), _bars(), "2026-06-03")[
        "reason"
    ] == "missing_entry_bar"
    assert reconcile_position(_position(direction="short"), _bars(), "2026-06-03")["reason"] == (
        "non_long_direction_v2"
    )


def test_build_persists_idempotent_ledger_and_state(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    state_path = tmp_path / "state.json"
    kwargs = dict(
        as_of="2026-06-03",
        positions=[_position(), _position(ticker="AMD", position_id=222, sleeve="discretionary", opened_by_strategy="legacy")],
        bars_fn=lambda ticker: _bars(),
        ledger_path=ledger,
        state_path=state_path,
    )
    state1 = build_live_drift_reconciliation(**kwargs)
    state2 = build_live_drift_reconciliation(**kwargs)  # same-day rerun

    assert state1["appended_rows"] == 2
    assert state2["appended_rows"] == 0  # idempotent per (asof, position_id)
    rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 2
    assert state1["reconciled_count"] == 2
    assert "core" in state1["buckets"] and "discretionary_legacy" in state1["buckets"]
    assert state1["production_impact"] == "observe_only_no_orders_no_ranking_no_sizing"
    assert json.loads(state_path.read_text(encoding="utf-8"))["rule_version"] == (
        "live_drift_reconciliation_v1"
    )


def test_drift_alert_requires_consecutive_breaches():
    def _rows(asof, drift):
        return [
            {
                "asof_date": asof,
                "strategy_bucket": "core",
                "reconcilable": True,
                "market_val": 10_000.0,
                "trajectory_drift_pct": drift,
                "fill_drift_pct": 0.0,
            }
        ]

    breach_days = [f"2026-06-{d:02d}" for d in range(1, ALERT_CONSECUTIVE_SESSIONS + 1)]
    ledger = []
    for day in breach_days:
        ledger.extend(_rows(day, -0.02))
    alert = evaluate_drift_alert(ledger)
    assert alert["consecutive_breach_sessions"] == ALERT_CONSECUTIVE_SESSIONS
    assert alert["trajectory_alert"] is True

    # one healthy session in the middle resets the streak
    ledger2 = []
    for i, day in enumerate(breach_days):
        ledger2.extend(_rows(day, -0.02 if i != 5 else 0.0))
    alert2 = evaluate_drift_alert(ledger2)
    assert alert2["trajectory_alert"] is False


def test_suspect_multi_fill_excluded_from_bucket_stats(tmp_path):
    # avg_cost 130 vs first-session modeled entry ~100 => +30% fake fill drift
    scaled_in = _position(avg_cost=130.0, market_val=1040.0, position_id=333)
    state = build_live_drift_reconciliation(
        as_of="2026-06-03",
        positions=[_position(), scaled_in],
        bars_fn=lambda ticker: _bars(),
        ledger_path=tmp_path / "ledger.jsonl",
        state_path=tmp_path / "state.json",
    )
    core = state["buckets"]["core"]
    assert core["reconciled"] == 2
    assert core["suspect_multi_fill"] == 1
    # aggregates come from the clean row only
    assert core["notional_usd"] == 1040.0


def test_positions_file_missing_is_fail_safe(tmp_path):
    state = build_live_drift_reconciliation(
        as_of="2026-06-03",
        positions_path=tmp_path / "nope.json",
        ledger_path=tmp_path / "ledger.jsonl",
        state_path=tmp_path / "state.json",
        persist=False,
    )
    assert state["status"] == "positions_unavailable"
