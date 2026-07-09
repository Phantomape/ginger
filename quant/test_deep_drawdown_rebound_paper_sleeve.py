"""Tests for the deep-drawdown rebound paper sleeve (exp-20260706-003).

The experiment closed REJECTED on full-history replay (mega-bear re-entry
bleed), so the sleeve is not wired into run.py. The module stays as recorded
evidence; these tests pin the episode policy and replay/daily parity so any
future episode-conditioned retry starts from verified semantics.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from deep_drawdown_rebound_paper_sleeve import (  # noqa: E402
    BUDGET_CONFIG,
    DEFAULT_CONFIG,
    compute_episode_flags,
    merge_bar_series,
    prep_and_build_deep_drawdown_rebound_snapshot,
    replay_deep_drawdown_rebound_trades,
)


def _bar(date, open_, high, low, close):
    return {"date": date, "open": open_, "high": high, "low": low, "close": close, "volume": 1e6}


def _crash_series():
    """100 flat sessions, then a crash below -12%, then a stabilization day."""
    # unique ascending synthetic dates
    rows = [
        _bar(f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}", 100, 101, 99, 100) for i in range(100)
    ]
    # crash: -14% close
    rows.append(_bar("2025-06-01", 95, 95, 84, 86))
    # continuation down day (no stabilization: down close)
    rows.append(_bar("2025-06-02", 86, 87, 82, 83))
    # stabilization: up close in upper half of range
    rows.append(_bar("2025-06-03", 83, 88, 82, 87))
    # forward sessions for entry + 5-day hold
    for i, price in enumerate((88, 89, 90, 91, 92, 93), start=4):
        rows.append(_bar(f"2025-06-{i:02d}", price, price + 1, price - 1, price))
    return rows


def test_episode_flags_trigger_and_stabilization():
    rows = _crash_series()
    flags = {f["date"]: f for f in compute_episode_flags(rows, DEFAULT_CONFIG)}

    assert flags["2025-06-01"]["in_episode"] is True  # -14% crosses the -12% trigger
    assert flags["2025-06-01"]["stabilization"] is False  # down close
    assert flags["2025-06-02"]["stabilization"] is False  # down close
    day3 = flags["2025-06-03"]
    assert day3["in_episode"] is True
    assert day3["stabilization"] is True  # up close, close_location (87-82)/(88-82)=0.83


def test_episode_resets_on_recovery_hysteresis():
    rows = _crash_series()
    # extend with a recovery above -5% of the rolling high (~100): close 97
    rows.append(_bar("2025-06-20", 96, 98, 95, 97))
    flags = compute_episode_flags(rows, DEFAULT_CONFIG)
    assert flags[-1]["in_episode"] is False


def test_replay_and_daily_snapshot_parity():
    """The same series must produce the same entry/exit through both paths."""
    rows = _crash_series()
    replay = replay_deep_drawdown_rebound_trades(rows, DEFAULT_CONFIG)
    assert len(replay["trades"]) == 1
    trade = replay["trades"][0]
    assert trade["signal_date"] == "2025-06-03"
    assert trade["entry_date"] == "2025-06-04"
    assert trade["exit_date"] == "2025-06-08"  # entry day counts as hold day 1

    snapshots = []
    dates = [row["date"] for row in rows]
    start_idx = dates.index("2025-06-03")
    working_state = {
        "schema_version": 1,
        "sleeve": "DEEP_DRAWDOWN_REBOUND_PAPER",
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }
    for idx in range(start_idx, len(rows)):
        as_of = dates[idx]
        visible = rows[: idx + 1]
        snapshot = prep_and_build_deep_drawdown_rebound_snapshot(
            as_of=as_of,
            qqq_ohlcv=visible,
            state=working_state,
            config={**DEFAULT_CONFIG, "min_history_days": 50},
            persist=False,
        )
        snapshots.append(snapshot)
        # carry the mutated state forward manually (persist=False path)
        working_state = {
            **working_state,
            "pending_entries": snapshot["pending_entries"],
            "open_positions": snapshot["open_positions"],
            "closed_positions": snapshot["closed_positions"],
        }

    assert snapshots[0]["new_pending_count"] == 1  # signal day queues next-open entry
    closed = working_state["closed_positions"]
    assert len(closed) == 1
    daily_trade = closed[0]
    assert daily_trade["entry_date"] == trade["entry_date"]
    assert daily_trade["exit_date"] == trade["exit_date"]
    assert abs(daily_trade["entry_price"] - trade["entry_price"]) < 1e-6
    assert abs(daily_trade["pnl_pct_net"] - trade["pnl_pct_net"]) < 1e-6


def test_daily_snapshot_same_day_rerun_does_not_double_admit():
    rows = _crash_series()
    dates = [row["date"] for row in rows]
    idx = dates.index("2025-06-03")
    visible = rows[: idx + 1]
    state = {
        "schema_version": 1,
        "sleeve": "DEEP_DRAWDOWN_REBOUND_PAPER",
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }
    cfg = {**DEFAULT_CONFIG, "min_history_days": 50}
    first = prep_and_build_deep_drawdown_rebound_snapshot(
        as_of="2025-06-03", qqq_ohlcv=visible, state=state, config=cfg, persist=False
    )
    state["pending_entries"] = first["pending_entries"]
    second = prep_and_build_deep_drawdown_rebound_snapshot(
        as_of="2025-06-03", qqq_ohlcv=visible, state=state, config=cfg, persist=False
    )
    assert first["new_pending_count"] == 1
    assert second["new_pending_count"] == 0  # decision_id dedupe
    assert second["pending_count"] == 1


def test_insufficient_history_is_fail_safe():
    rows = _crash_series()[:30]
    snapshot = prep_and_build_deep_drawdown_rebound_snapshot(
        as_of=rows[-1]["date"], qqq_ohlcv=rows, persist=False
    )
    assert snapshot["error"] == "insufficient_history"
    assert snapshot["trade_enabled"] is False


def _two_signal_series():
    """Crash series with a second stabilization inside the same episode."""
    rows = _crash_series()
    # dip inside the still-active episode (close 93 -> -7%, above the -5% reset)
    rows.append(_bar("2025-06-10", 92, 92, 87, 88))  # down close
    rows.append(_bar("2025-06-11", 88, 93, 88, 92))  # stabilization #2
    for i, price in enumerate((93, 94, 95, 96, 97), start=12):
        rows.append(_bar(f"2025-06-{i:02d}", price, price + 1, price - 1, price))
    return rows


def test_replay_budget_limits_entries_per_episode():
    rows = _two_signal_series()
    unbudgeted = replay_deep_drawdown_rebound_trades(rows, DEFAULT_CONFIG)
    budgeted = replay_deep_drawdown_rebound_trades(rows, BUDGET_CONFIG)

    assert len(unbudgeted["trades"]) == 2
    assert len(budgeted["trades"]) == 1
    assert budgeted["trades"][0]["signal_date"] == "2025-06-03"  # first only


def test_daily_snapshot_respects_episode_budget():
    rows = _two_signal_series()
    dates = [row["date"] for row in rows]
    idx = dates.index("2025-06-11")  # second stabilization of the same episode
    visible = rows[: idx + 1]
    state = {
        "schema_version": 1,
        "sleeve": "DEEP_DRAWDOWN_REBOUND_PAPER",
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [
            {
                "decision_id": "deep_drawdown_rebound:QQQ:2025-06-03",
                "ticker": "QQQ",
                "episode_start_date": "2025-06-01",
                "paper_status": "closed",
                "pnl": 100.0,
            }
        ],
        "skipped_days": [],
    }
    budget_cfg = {**BUDGET_CONFIG, "min_history_days": 50}
    snapshot = prep_and_build_deep_drawdown_rebound_snapshot(
        as_of="2025-06-11", qqq_ohlcv=visible, state=state, config=budget_cfg, persist=False
    )
    assert snapshot["candidate"] is not None  # signal fires
    assert snapshot["new_pending_count"] == 0  # but episode budget is spent

    unbudgeted_cfg = {**DEFAULT_CONFIG, "min_history_days": 50}
    snapshot2 = prep_and_build_deep_drawdown_rebound_snapshot(
        as_of="2025-06-11", qqq_ohlcv=visible, state=state, config=unbudgeted_cfg, persist=False
    )
    assert snapshot2["new_pending_count"] == 1  # unlimited shape still admits


def test_run_py_daily_wiring_uses_shared_helper_with_budget_config():
    import ast

    source = (QUANT / "run.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    budget_config_call = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "deep_drawdown_rebound_paper_sleeve":
            imported.update(
                alias.asname or alias.name for alias in node.names
            )
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == (
            "prep_and_build_deep_drawdown_rebound_snapshot"
        ):
            for kw in node.keywords:
                if kw.arg == "config" and getattr(kw.value, "id", None) == (
                    "DEEP_DRAWDOWN_REBOUND_BUDGET_CONFIG"
                ):
                    budget_config_call = True
    assert "prep_and_build_deep_drawdown_rebound_snapshot" in imported
    assert "empty_deep_drawdown_rebound_snapshot" in imported
    assert "DEEP_DRAWDOWN_REBOUND_BUDGET_CONFIG" in imported
    assert budget_config_call  # the daily path ships the budget=1 bundle


def test_merge_bar_series_prefers_warehouse_on_overlap():
    archive = [_bar("2023-08-25", 1, 1, 1, 1), _bar("2023-08-24", 1, 1, 1, 1)]
    warehouse = [_bar("2023-08-25", 2, 2, 2, 2), _bar("2023-08-29", 2, 2, 2, 2)]
    merged = merge_bar_series(archive, warehouse)
    assert [row["date"] for row in merged] == ["2023-08-24", "2023-08-25", "2023-08-29"]
    assert merged[1]["close"] == 2
