from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd

from report_generator import generate_daily_report
from sec_10k_forward_watch import (
    build_sec_10k_forward_watch,
    persist_sec_10k_forward_watch,
)


def _df(
    *,
    start_close: float = 10.0,
    volume: int = 1_000_000,
    days: int = 25,
) -> pd.DataFrame:
    start = date(2026, 3, 20)
    rows = []
    for idx in range(days):
        close = start_close + idx * 0.25
        rows.append(
            {
                "Date": (start + timedelta(days=idx)).isoformat(),
                "Open": round(close * 0.99, 4),
                "High": round(close * 1.01, 4),
                "Low": round(close * 0.98, 4),
                "Close": round(close, 4),
                "Volume": volume,
            }
        )
    return pd.DataFrame(rows)


def _event(ticker: str = "ACME") -> dict:
    return {
        "ticker": ticker,
        "cik": "0000000001",
        "accession_number": f"0000000001-26-{ticker}",
        "form_type": "10-K",
        "form_base": "10-K",
        "filing_date": "2026-04-13",
        "accepted_at": "2026-04-13T21:30:00",
        "usable_trade_date": "2026-04-14",
        "archive_url": f"https://example.com/{ticker}.htm",
        "pit_safe_flag": True,
        "pit_source": "sec_submissions_recent",
        "is_amendment": False,
    }


def _core_signal() -> dict:
    return {
        "ticker": "AAPL",
        "strategy": "trend_long",
        "action": "BUY",
        "sector": "Technology",
        "entry_price": 201.25,
        "confidence_score": 0.9,
        "trade_quality_score": 0.86,
    }


def test_build_watch_flags_outside_universe_liquidity_candidate():
    snapshot = build_sec_10k_forward_watch(
        as_of="2026-04-14",
        sec_filing_events=[_event()],
        ohlcv_by_ticker={"ACME": _df(start_close=10.0, volume=1_000_000)},
        current_universe={"AAPL", "MSFT"},
        core_signals=[_core_signal()],
    )

    assert snapshot["trade_enabled"] is False
    assert snapshot["ten_k_event_count"] == 1
    assert snapshot["outside_universe_10k_count"] == 1
    assert snapshot["candidate_count"] == 1
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "ACME"
    assert candidate["eligible"] is True
    assert candidate["liquidity_bucket"] == "adv_5m_20m"
    assert candidate["same_day_core_alternative_count"] == 1
    assert candidate["production_impact"]["alters_orders"] is False


def test_build_watch_excludes_current_universe_10k_by_default():
    snapshot = build_sec_10k_forward_watch(
        as_of="2026-04-14",
        sec_filing_events=[_event("AAPL")],
        ohlcv_by_ticker={"AAPL": _df(start_close=200.0, volume=2_000_000)},
        current_universe={"AAPL", "MSFT"},
    )

    assert snapshot["ten_k_event_count"] == 1
    assert snapshot["candidate_count"] == 0
    assert snapshot["all_10k_rows"][0]["eligibility_status"] == "current_universe_excluded"
    assert snapshot["all_10k_rows"][0]["liquidity_qualified"] is True


def test_build_watch_excludes_low_liquidity_outside_universe_candidate():
    snapshot = build_sec_10k_forward_watch(
        as_of="2026-04-14",
        sec_filing_events=[_event("TINY")],
        ohlcv_by_ticker={"TINY": _df(start_close=2.0, volume=50_000)},
        current_universe={"AAPL", "MSFT"},
    )

    assert snapshot["candidate_count"] == 0
    row = snapshot["all_10k_rows"][0]
    assert row["eligibility_status"] == "low_liquidity"
    assert row["liquidity_bucket"] == "adv_lt_5m"


def test_persist_watch_appends_candidates_once(tmp_path):
    snapshot = build_sec_10k_forward_watch(
        as_of="2026-04-14",
        sec_filing_events=[_event()],
        ohlcv_by_ticker={"ACME": _df(start_close=10.0, volume=1_000_000)},
        current_universe={"AAPL", "MSFT"},
    )
    ledger = tmp_path / "watch.jsonl"
    summary = tmp_path / "summary.json"

    first = persist_sec_10k_forward_watch(
        snapshot,
        ledger_path=ledger,
        summary_path=summary,
    )
    second = persist_sec_10k_forward_watch(
        snapshot,
        ledger_path=ledger,
        summary_path=summary,
    )

    lines = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert first["persistence"]["appended_count"] == 1
    assert second["persistence"]["appended_count"] == 0
    assert len(lines) == 1
    assert json.loads(summary.read_text(encoding="utf-8"))["ledger_row_count"] == 1


def test_report_generator_renders_sec_10k_watch_without_orders():
    snapshot = build_sec_10k_forward_watch(
        as_of="2026-04-14",
        sec_filing_events=[_event()],
        ohlcv_by_ticker={"ACME": _df(start_close=10.0, volume=1_000_000)},
        current_universe={"AAPL", "MSFT"},
        core_signals=[_core_signal()],
    )

    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        sec_10k_forward_watch=snapshot,
    )

    assert "SEC 10-K LIQUIDITY WATCH" in report
    assert "Trade enabled: False" in report
    assert "observe only" in report
