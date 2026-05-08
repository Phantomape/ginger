from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd

from report_generator import generate_daily_report
from platform_rs20_watch import (
    build_platform_rs20_forward_watch,
    persist_platform_rs20_forward_watch,
)


def _df(
    *,
    start_close: float,
    end_close: float,
    current_gap: float = 0.01,
) -> pd.DataFrame:
    start = date(2026, 4, 1)
    rows = []
    for idx in range(21):
        value = start_close + (end_close - start_close) * (idx / 20)
        if idx == 20:
            previous = rows[-1]["Close"]
            row_open = previous * (1.0 + current_gap)
        else:
            row_open = value * 0.99
        rows.append(
            {
                "Date": (start + timedelta(days=idx)).isoformat(),
                "Open": round(row_open, 4),
                "High": round(value * 1.01, 4),
                "Low": round(value * 0.99, 4),
                "Close": round(value, 4),
                "Volume": 1000 + idx,
            }
        )
    return pd.DataFrame(rows)


def _entry_plan(ticker: str = "APP") -> dict:
    return {
        "deferred_breakout_signals": [
            {
                "ticker": ticker,
                "strategy": "breakout_long",
                "sector": "Technology",
                "available_slots": 1,
                "trade_quality_score": 0.91,
                "confidence_score": 1.0,
                "entry_price": 115.0,
                "stop_price": 110.0,
                "target_price": 130.0,
            }
        ],
        "slot_sliced_signals": [],
    }


def test_build_watch_flags_platform_rs20_no_gap_candidate():
    snapshot = build_platform_rs20_forward_watch(
        as_of="2026-04-21",
        entry_execution_plan=_entry_plan(),
        ohlcv_by_ticker={
            "APP": _df(start_close=100.0, end_close=120.0, current_gap=0.01),
            "SPY": _df(start_close=100.0, end_close=102.0, current_gap=0.0),
        },
        features_by_ticker={"APP": {"days_to_earnings": 12}},
    )

    assert snapshot["trade_enabled"] is False
    assert snapshot["platform_missed_count"] == 1
    assert snapshot["platform_rs20_missed_count"] == 1
    assert snapshot["no_gap_rs20_watch_count"] == 1
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "APP"
    assert candidate["decision"] == "scarce_slot_breakout_deferred"
    assert candidate["no_gap_up_3pct"] is True
    assert candidate["is_platform_rs20_leader"] is True
    assert "rs20_leader" in candidate["tags"]
    assert candidate["production_impact"]["alters_orders"] is False


def test_build_watch_excludes_gap_up_candidate_from_no_gap_watch():
    snapshot = build_platform_rs20_forward_watch(
        as_of="2026-04-21",
        entry_execution_plan=_entry_plan("META"),
        ohlcv_by_ticker={
            "META": _df(start_close=100.0, end_close=120.0, current_gap=0.05),
            "SPY": _df(start_close=100.0, end_close=102.0, current_gap=0.0),
        },
    )

    assert snapshot["platform_missed_count"] == 1
    assert snapshot["platform_rs20_missed_count"] == 1
    assert snapshot["no_gap_rs20_watch_count"] == 0
    assert snapshot["candidates"] == []
    assert snapshot["all_platform_missed_rows"][0]["no_gap_up_3pct"] is False
    assert "gap_up_3pct" in snapshot["all_platform_missed_rows"][0]["tags"]


def test_persist_watch_appends_candidates_once(tmp_path):
    snapshot = build_platform_rs20_forward_watch(
        as_of="2026-04-21",
        entry_execution_plan=_entry_plan(),
        ohlcv_by_ticker={
            "APP": _df(start_close=100.0, end_close=120.0, current_gap=0.01),
            "SPY": _df(start_close=100.0, end_close=102.0, current_gap=0.0),
        },
    )
    ledger = tmp_path / "watch.jsonl"
    summary = tmp_path / "summary.json"

    first = persist_platform_rs20_forward_watch(
        snapshot,
        ledger_path=ledger,
        summary_path=summary,
    )
    second = persist_platform_rs20_forward_watch(
        snapshot,
        ledger_path=ledger,
        summary_path=summary,
    )

    lines = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert first["persistence"]["appended_count"] == 1
    assert second["persistence"]["appended_count"] == 0
    assert len(lines) == 1
    assert json.loads(summary.read_text(encoding="utf-8"))["ledger_row_count"] == 1


def test_report_generator_renders_platform_rs20_watch_without_orders():
    snapshot = build_platform_rs20_forward_watch(
        as_of="2026-04-21",
        entry_execution_plan=_entry_plan(),
        ohlcv_by_ticker={
            "APP": _df(start_close=100.0, end_close=120.0, current_gap=0.01),
            "SPY": _df(start_close=100.0, end_close=102.0, current_gap=0.0),
        },
    )

    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        platform_rs20_watch=snapshot,
    )

    assert "PLATFORM RS20 NO-GAP WATCH" in report
    assert "Trade enabled: False" in report
    assert "observe only" in report
