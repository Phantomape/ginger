"""Tests for the read-only live position-control ledger."""

from __future__ import annotations

import json
from pathlib import Path

from live_position_control_ledger import (
    build_position_control_ledger,
    parse_daily_report,
)


REPORT = """
PORTFOLIO HEAT: 3.5%  (OK to add)
  Positions: 11  |  Resting orders: 19 (10 target-limit, 9 stop)  |  Exit-now flags: 2  |  Warnings: 4
  These make backtest/production fills real; run.py does NOT submit them.

  MAINTAIN these resting orders:
         AMD    SELL STOP  @     458.60 x7 GTC  [stop]
         APP    SELL STOP  @     474.39 x8 GTC  [stop]
         APP    SELL LIMIT @     609.69 x8 GTC  [target]
         CRDO   SELL STOP  @     225.70 x15 GTC  [stop]
         CRDO   SELL LIMIT @     314.40 x15 GTC  [target]

  EXIT NOW (level already reached - resting order can't capture it):
    COHR   stop   current 314.13 <= static_entry stop 338.66; stop already breached - exit now.
    GEV    stop   current 1077.08 <= static_entry stop 1079.60; stop already breached - exit now.
  ! AMD: price 516.11 is past recorded target 209.06 - runner protected by trailed_fallback stop 458.60; no resting limit emitted.
  ! AMD: emitting TRAILED stop 458.60 - entry stop could not be reconstructed; static entry stop is EV-optimal.
  ! APP: emitting TRAILED stop 474.39 - entry stop could not be reconstructed; static entry stop is EV-optimal.

ENTRY SLOTS (core strategy): 4 available
"""


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_parse_report_extracts_brackets_exit_now_and_warnings(tmp_path: Path) -> None:
    report_path = tmp_path / "report_20260707.txt"
    report_path.write_text(REPORT, encoding="utf-8")

    parsed = parse_daily_report(REPORT, report_path)

    assert parsed["report_date"] == "2026-07-07"
    assert parsed["portfolio_heat_status"] == "OK to add"
    assert parsed["ok_to_add_reported"] is True
    assert parsed["entry_slots_available"] == 4
    assert parsed["bracket_summary"]["resting_orders"] == 19
    assert parsed["orders_by_ticker"]["APP"][1]["bracket_kind"] == "target"
    assert parsed["exit_now_by_ticker"]["COHR"][0]["trigger_kind"] == "stop"
    assert "stale_target" in parsed["warnings_by_ticker"]["AMD"][0]["flags"]
    assert "fallback_stop" in parsed["warnings_by_ticker"]["AMD"][1]["flags"]


def test_build_position_control_ledger_blocks_ok_to_add_and_is_idempotent(tmp_path: Path) -> None:
    report_path = tmp_path / "report_20260707.txt"
    positions_path = tmp_path / "open_positions.json"
    live_drift_path = tmp_path / "live_drift_state.json"
    ledger_path = tmp_path / "position_control" / "ledger.jsonl"
    state_path = tmp_path / "position_control" / "state.json"
    report_path.write_text(REPORT, encoding="utf-8")
    _write_json(
        positions_path,
        {
            "as_of": "2026-07-08",
            "positions": [
                {
                    "ticker": "CRDO",
                    "direction": "long",
                    "shares": 15,
                    "avg_cost": 262,
                    "entry_date": "2026-06-12",
                    "target_price": 314.4,
                    "stop_price": 216.5,
                    "opened_by_strategy": "fomo",
                    "sleeve": "fomo",
                    "risk_notes": "systematic entry",
                    "position_id": 1,
                },
                {
                    "ticker": "GEV",
                    "direction": "long",
                    "shares": 3,
                    "avg_cost": 1160,
                    "entry_date": "2026-07-01",
                    "target_price": 1392,
                    "stop_price": 1000.83,
                    "opened_by_strategy": "alpha_score_market_regime",
                    "sleeve": "alpha_score_market_regime",
                    "risk_notes": "paper mirror",
                    "position_id": 2,
                },
            ],
            "observations": [
                {"ticker": "APP", "shares": 8, "sleeve": "legacy", "position_id": 3}
            ],
        },
    )
    _write_json(live_drift_path, {"asof_date": "2026-07-07", "status": "ok"})

    first = build_position_control_ledger(
        report_path=report_path,
        positions_path=positions_path,
        live_drift_state_path=live_drift_path,
        ledger_path=ledger_path,
        state_path=state_path,
    )
    second = build_position_control_ledger(
        report_path=report_path,
        positions_path=positions_path,
        live_drift_state_path=live_drift_path,
        ledger_path=ledger_path,
        state_path=state_path,
    )

    state = first["state"]
    assert state["ok_to_add_reported"] is True
    assert state["ok_to_add_control_pass"] is False
    assert "exit_now" in state["ok_to_add_control_blockers"]
    assert "fallback_stop" in state["ok_to_add_control_blockers"]
    assert "manual_bracket_orders_not_broker_confirmed" in state["ok_to_add_control_blockers"]
    assert "report_open_positions_asof_mismatch" in state["ok_to_add_control_blockers"]
    assert first["append_result"]["rows_appended"] > 0
    assert second["append_result"]["rows_appended"] == 0
    assert ledger_path.exists()


def test_report_only_rows_are_kept(tmp_path: Path) -> None:
    report_path = tmp_path / "report_20260707.txt"
    positions_path = tmp_path / "open_positions.json"
    ledger_path = tmp_path / "ledger.jsonl"
    state_path = tmp_path / "state.json"
    report_path.write_text(REPORT, encoding="utf-8")
    _write_json(positions_path, {"as_of": "2026-07-07", "positions": []})

    result = build_position_control_ledger(
        report_path=report_path,
        positions_path=positions_path,
        live_drift_state_path=tmp_path / "missing_live_drift.json",
        ledger_path=ledger_path,
        state_path=state_path,
    )

    assert result["state"]["report_only_row_count"] >= 1
    assert any(row["ticker"] == "GEV" and row["row_source"] == "report_only" for row in result["rows"])
    assert "report_only_control_row" in result["state"]["ok_to_add_control_blockers"]

