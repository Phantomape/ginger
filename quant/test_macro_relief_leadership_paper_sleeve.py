from __future__ import annotations

from datetime import date, timedelta

from quant.default_off_alpha_attribution import build_default_off_alpha_attribution_report
from quant.macro_relief_leadership_paper_sleeve import (
    SLEEVE_NAME,
    SOURCE_RULE_VERSION,
    build_macro_relief_leadership_snapshot,
    empty_macro_relief_leadership_state,
)
from quant.report_generator import generate_daily_report


def _rows(
    *,
    start_price: float,
    daily_step: float,
    event_gain: float = 0.0,
    event_date: str = "2025-01-15",
    days: int = 145,
) -> list[dict[str, float | str]]:
    start = date(2024, 10, 1)
    price = start_price
    out: list[dict[str, float | str]] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        day_text = day.isoformat()
        open_price = price
        gain = event_gain if day_text == event_date else daily_step
        close = open_price * (1.0 + gain)
        high = max(open_price, close) * 1.002
        low = min(open_price, close) * 0.998
        volume = 8_000_000 if day_text == event_date else 5_000_000
        out.append(
            {
                "date": day_text,
                "open": round(open_price, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": volume,
            }
        )
        price = close
    return out


def _universe(*tickers: str) -> dict:
    return {
        "status": "test_broad_market_universe",
        "tickers": list(tickers),
        "records": {
            ticker: {"sector": "Technology", "industry": "Software"}
            for ticker in tickers
        },
    }


def test_macro_relief_leadership_selects_top_two_without_orders() -> None:
    ohlcv = {
        "SPY": _rows(start_price=100.0, daily_step=0.0008, event_gain=0.007),
        "QQQ": _rows(start_price=100.0, daily_step=0.0010, event_gain=0.009),
        "AAA": _rows(start_price=70.0, daily_step=0.0018, event_gain=0.036),
        "BBB": _rows(start_price=60.0, daily_step=0.0016, event_gain=0.028),
        "CCC": _rows(start_price=55.0, daily_step=0.0015, event_gain=0.021),
    }

    snapshot = build_macro_relief_leadership_snapshot(
        as_of="2025-01-15",
        ohlcv_by_ticker=ohlcv,
        candidate_universe=_universe("AAA", "BBB", "CCC"),
        state=empty_macro_relief_leadership_state(),
        persist=False,
    )

    assert snapshot["sleeve"] == SLEEVE_NAME
    assert snapshot["source_rule_version"] == SOURCE_RULE_VERSION
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["alters_orders"] is False
    assert snapshot["macro_relief_context"]["passed"] is True
    assert snapshot["raw_candidate_count"] == 3
    assert snapshot["candidate_count"] == 2
    assert [row["ticker"] for row in snapshot["candidates"]] == ["AAA", "BBB"]
    assert snapshot["new_pending_count"] == 2
    assert snapshot["pending_entries"][0]["paper_status"] == "pending_entry"
    assert snapshot["pending_entries"][0]["entry_timing"] == "next_session_open"


def test_macro_relief_leadership_replay_uses_next_open_and_10_day_close() -> None:
    ohlcv = {
        "SPY": _rows(start_price=100.0, daily_step=0.0008, event_gain=0.007),
        "QQQ": _rows(start_price=100.0, daily_step=0.0010, event_gain=0.009),
        "AAA": _rows(start_price=70.0, daily_step=0.0018, event_gain=0.036),
    }

    first = build_macro_relief_leadership_snapshot(
        as_of="2025-01-15",
        ohlcv_by_ticker=ohlcv,
        candidate_universe=_universe("AAA"),
        state=empty_macro_relief_leadership_state(),
        persist=False,
    )
    state = {
        "schema_version": 1,
        "sleeve": SLEEVE_NAME,
        "pending_entries": first["pending_entries"],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }
    snapshots = {}
    for offset in range(1, 11):
        day = (date(2025, 1, 15) + timedelta(days=offset)).isoformat()
        snapshots[day] = build_macro_relief_leadership_snapshot(
            as_of=day,
            ohlcv_by_ticker=ohlcv,
            candidate_universe=_universe("AAA"),
            state=state,
            persist=False,
        )
        state = {
            "schema_version": 1,
            "sleeve": SLEEVE_NAME,
            "pending_entries": snapshots[day]["pending_entries"],
            "open_positions": snapshots[day]["open_positions"],
            "closed_positions": snapshots[day]["closed_positions"],
            "skipped_days": [],
        }
    second = snapshots["2025-01-16"]
    final = snapshots["2025-01-25"]

    assert second["filled_count"] == 1
    assert second["open_positions"][0]["entry_date"] == "2025-01-16"
    assert final["closed_count_today"] == 1
    assert final["closed_positions_today"][0]["exit_date"] == "2025-01-25"
    assert final["closed_positions_today"][0]["trade_enabled"] is False


def test_macro_relief_leadership_skips_non_macro_event_day() -> None:
    ohlcv = {
        "SPY": _rows(start_price=100.0, daily_step=0.0008, event_gain=0.007),
        "QQQ": _rows(start_price=100.0, daily_step=0.0010, event_gain=0.009),
        "AAA": _rows(start_price=70.0, daily_step=0.0018, event_gain=0.036),
    }

    snapshot = build_macro_relief_leadership_snapshot(
        as_of="2025-01-16",
        ohlcv_by_ticker=ohlcv,
        candidate_universe=_universe("AAA"),
        state=empty_macro_relief_leadership_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["macro_relief_context"]["passed"] is False
    assert snapshot["trade_enabled"] is False


def test_default_off_attribution_and_report_include_macro_relief_surface() -> None:
    snapshot = {
        "sleeve": SLEEVE_NAME,
        "source_rule_version": SOURCE_RULE_VERSION,
        "trade_enabled": False,
        "candidate_count": 1,
        "raw_candidate_count": 3,
        "candidate_universe": {
            "status": "test_broad_market_universe",
            "ticker_count": 3,
        },
        "context_scan": {"macro_relief_days": 1},
        "macro_relief_context": {"passed": True},
        "candidates": [
            {
                "ticker": "AAA",
                "candidate_score": 0.58,
                "candidate_relative_vs_spy": 0.02,
                "signal_date": "2025-01-15",
                "paper_notional_usd": 4_000.0,
            }
        ],
        "forward_paper_gate": {
            "passed": False,
            "status": "blocked",
            "reasons": ["min_closed_trades"],
            "metrics": {"closed_trades": 0, "realized_pnl": 0.0},
        },
    }

    attribution = build_default_off_alpha_attribution_report(
        as_of="2025-01-15",
        macro_relief_leadership_paper_sleeve=snapshot,
    )
    surfaces = {row["name"]: row for row in attribution["surfaces"]}

    assert surfaces["macro_relief_leadership"]["label"] == "MACRO_RELIEF_LEADERSHIP_PAPER"
    assert surfaces["macro_relief_leadership"]["trade_enabled"] is False
    assert surfaces["macro_relief_leadership"]["extra_metrics"]["macro_relief_days"] == 1
    assert "min_closed_trades" in surfaces["macro_relief_leadership"]["blockers"]

    report = generate_daily_report(
        signals=[],
        macro_relief_leadership_paper_sleeve=snapshot,
    )

    assert "MACRO RELIEF LEADERSHIP PAPER SLEEVE" in report
    assert "AAA: score=0.58" in report
