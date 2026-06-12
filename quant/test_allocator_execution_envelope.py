"""Envelope/kill-switch parity tests for the accepted allocator sleeve (exp-20260612-022)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant import accepted_helper_source_priority_allocator_paper_sleeve as sleeve


def _trade(entry, exit_, pnl, ticker="AAA", adv=50_000_000.0):
    return {
        "ticker": ticker,
        "entry_date": entry,
        "exit_date": exit_,
        "pnl": pnl,
        "candidate_avg_dollar_volume_20d": adv,
    }


def test_envelope_constants_complete():
    env = sleeve.EXECUTION_ENVELOPE
    required = [
        "rule_version", "mode", "bucket_notional_usd", "base_notional_usd",
        "max_concurrent_positions", "min_avg_dollar_volume_20d",
        "order_semantics", "missed_fill_policy", "halt_policy",
        "kill_switch_basis", "kill_switch_drawdown_pct", "core_displacement",
        "slippage_model", "trade_enabled",
    ]
    for key in required:
        assert key in env and env[key] is not None
    assert env["trade_enabled"] is False
    assert env["core_displacement"] == 0


def test_kill_switch_triggers_on_realized_drawdown():
    bucket = float(sleeve.EXECUTION_ENVELOPE["bucket_notional_usd"])
    threshold = float(sleeve.EXECUTION_ENVELOPE["kill_switch_drawdown_pct"])
    loss = -(bucket * threshold / 2 + 1.0)
    trades = [
        _trade("2026-01-05", "2026-01-20", loss),
        _trade("2026-01-06", "2026-01-21", loss, ticker="BBB"),
    ]
    state = sleeve.evaluate_kill_switch_state(trades)
    assert state["triggered"] is True
    assert state["trigger_exit_date"] == "2026-01-21"
    ok = sleeve.evaluate_kill_switch_state([_trade("2026-01-05", "2026-01-20", 100.0)])
    assert ok["triggered"] is False


def test_concurrency_cap_skips_overlapping_trades():
    max_open = int(sleeve.EXECUTION_ENVELOPE["max_concurrent_positions"])
    trades = [
        _trade(f"2026-02-{day:02d}", f"2026-02-{day + 14:02d}", 10.0, ticker=f"T{day}")
        for day in range(1, max_open + 3)
    ]
    kept, skipped, audit = sleeve.apply_execution_envelope_to_trades(trades)
    assert len(kept) == max_open
    assert audit["skip_reasons"].get("max_concurrent_positions") == 2


def test_kill_switch_halts_remaining_stream():
    bucket = float(sleeve.EXECUTION_ENVELOPE["bucket_notional_usd"])
    threshold = float(sleeve.EXECUTION_ENVELOPE["kill_switch_drawdown_pct"])
    big_loss = -(bucket * threshold + 1.0)
    trades = [
        _trade("2026-03-02", "2026-03-05", big_loss),
        _trade("2026-03-09", "2026-03-20", 50.0, ticker="BBB"),
        _trade("2026-03-10", "2026-03-21", 50.0, ticker="CCC"),
    ]
    kept, skipped, audit = sleeve.apply_execution_envelope_to_trades(trades)
    assert len(kept) == 1
    assert audit["kill_switch_halted"] is True
    assert audit["skip_reasons"].get("kill_switch_halt") == 2


def test_adv_floor_skips_thin_rows():
    thin = _trade("2026-04-01", "2026-04-10", 10.0, adv=1_000_000.0)
    kept, skipped, audit = sleeve.apply_execution_envelope_to_trades([thin])
    assert not kept
    assert audit["skip_reasons"].get("below_min_adv_floor") == 1


def test_daily_snapshot_exposes_envelope_and_kill_switch():
    cfg = sleeve._config()
    state = sleeve.empty_accepted_helper_source_priority_allocator_state()
    payload = sleeve._snapshot_payload(
        state,
        as_of="2026-06-12",
        source_rows=[],
        selected_rows=[],
        rejected=[],
        source_coverage={},
        priority_audit={},
        new_pending_entries=[],
        filled_today=[],
        closed_today=[],
        rows_by_ticker={},
        config=cfg,
    )
    assert payload["execution_envelope"]["rule_version"] == sleeve.EXECUTION_ENVELOPE["rule_version"]
    ks = payload["kill_switch_state"]
    assert ks["rule_version"] == sleeve.EXECUTION_ENVELOPE["rule_version"]
    assert ks["triggered"] is False
    assert payload["trade_enabled"] is False


def test_v2_profit_giveback_does_not_false_trigger():
    # v1 failure mode (exp-20260612-022): giveback of accumulated profits
    # tripped the fixed-bucket basis; v2 measures against realized-equity peak.
    bucket = float(sleeve.EXECUTION_ENVELOPE["bucket_notional_usd"])
    gain = bucket * 0.625
    giveback = -(bucket * 0.125)
    trades = [
        _trade("2026-05-01", "2026-05-10", gain),
        _trade("2026-05-11", "2026-05-20", giveback, ticker="BBB"),
    ]
    state = sleeve.evaluate_kill_switch_state(trades)
    assert state["triggered"] is False
    assert state["max_realized_drawdown_pct_of_peak_equity"] < 0.15
