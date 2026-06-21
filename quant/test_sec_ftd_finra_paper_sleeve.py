from __future__ import annotations

from datetime import date, timedelta

from quant.default_off_alpha_attribution import build_default_off_alpha_attribution_report
from quant.sec_ftd_finra_paper_sleeve import (
    FINRA_CONFIRMATION_RULE_VERSION,
    FTD_SOURCE_RULE_VERSION,
    RULE_VERSION,
    build_sec_ftd_finra_paper_sleeve_snapshot,
    empty_sec_ftd_finra_paper_state,
)


def _rows(
    *,
    base: float = 50.0,
    step: float = 0.10,
    days: int = 72,
    breakout_day: int | None = None,
    breakout_close: float | None = None,
    spike_day: int | None = None,
    spike_volume: float = 2_000_000.0,
) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(days):
        close = base + step * idx
        if breakout_day is not None and idx == breakout_day:
            close = breakout_close if breakout_close is not None else close * 1.15
        volume = 1_000_000.0
        if spike_day is not None and idx == spike_day:
            volume = spike_volume
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": round(close * 0.995, 4),
                "high": round(close * 1.01, 4),
                "low": round(close * 0.99, 4),
                "close": round(close, 4),
                "volume": volume,
            }
        )
    return rows


def _ohlcv(asof_idx: int = 60) -> dict[str, list[dict]]:
    rows = {
        "SPY": _rows(base=100.0, step=0.05),
        "WIN": _rows(
            base=80.0,
            step=0.08,
            breakout_day=asof_idx,
            breakout_close=102.0,
            spike_day=asof_idx,
            spike_volume=2_500_000.0,
        ),
        "LOWDTC": _rows(
            base=70.0,
            step=0.08,
            breakout_day=asof_idx,
            breakout_close=96.0,
            spike_day=asof_idx,
            spike_volume=2_400_000.0,
        ),
    }
    for ticker in ("WIN", "LOWDTC"):
        close = rows[ticker][asof_idx]["close"]
        rows[ticker][asof_idx]["high"] = round(close * 1.001, 4)
        rows[ticker][asof_idx]["low"] = round(close * 0.97, 4)
    return rows


def _ftd_rows() -> list[dict]:
    return [
        {
            "ticker": "WIN",
            "settlement_date": "2026-01-31",
            "publication_date": "2026-02-16",
            "ftd_shares": 200_000,
            "ftd_price": 50.0,
            "ftd_notional": 10_000_000.0,
        },
        {
            "ticker": "LOWDTC",
            "settlement_date": "2026-01-31",
            "publication_date": "2026-02-16",
            "ftd_shares": 220_000,
            "ftd_price": 40.0,
            "ftd_notional": 8_800_000.0,
        },
    ]


def _finra_rows() -> list[dict]:
    return [
        {
            "ticker": "WIN",
            "settlement_date": "2026-02-13",
            "publication_date": "2026-02-25",
            "days_to_cover": 5.0,
            "short_interest_change_pct": 12.0,
            "short_interest": 1_000_000,
            "previous_short_interest": 890_000,
        },
        {
            "ticker": "LOWDTC",
            "settlement_date": "2026-02-13",
            "publication_date": "2026-02-25",
            "days_to_cover": 2.0,
            "short_interest_change_pct": 20.0,
            "short_interest": 1_000_000,
            "previous_short_interest": 800_000,
        },
    ]


def test_sec_ftd_finra_snapshot_admits_candidate_without_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][60]["date"]

    snapshot = build_sec_ftd_finra_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["WIN", "LOWDTC"],
        ftd_rows=_ftd_rows(),
        finra_rows=_finra_rows(),
        state=empty_sec_ftd_finra_paper_state(),
        persist=False,
        config={"allow_network_fetch": False},
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False
    assert snapshot["ftd_pressure"]["rule_version"] == FTD_SOURCE_RULE_VERSION
    assert snapshot["finra_confirmation"]["rule_version"] == FINRA_CONFIRMATION_RULE_VERSION
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "WIN"
    assert candidate["rule_version"] == RULE_VERSION
    assert candidate["ftd_finra_trade_enabled"] is False
    assert candidate["ftd_finra_alters_orders"] is False
    assert candidate["finra_days_to_cover"] == 5.0
    assert candidate["finra_short_interest_change_pct"] == 12.0
    assert snapshot["new_pending_entries"][0]["notional"] == 4_000.0
    assert snapshot["candidate_reject_counts"]["finra_days_to_cover_below_threshold"] == 1


def test_same_day_core_overlap_blocks_candidate():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][60]["date"]

    snapshot = build_sec_ftd_finra_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["WIN"],
        ftd_rows=_ftd_rows(),
        finra_rows=_finra_rows(),
        same_day_core_tickers=["WIN"],
        state=empty_sec_ftd_finra_paper_state(),
        persist=False,
        config={"allow_network_fetch": False},
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["candidate_reject_counts"]["same_ticker_core_overlap"] == 1


def test_stale_missing_asof_price_does_not_fill_pending_entry():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][60]["date"]
    stale_ohlcv = dict(ohlcv)
    stale_ohlcv["WIN"] = [row for row in ohlcv["WIN"] if row["date"] != as_of]
    state = empty_sec_ftd_finra_paper_state()
    state["pending_entries"].append(
        {
            "decision_id": "test",
            "sleeve": "SEC_FTD_FINRA_CONFIRMED_PAPER",
            "ticker": "WIN",
            "created_asof": (date.fromisoformat(as_of) - timedelta(days=1)).isoformat(),
            "status": "pending_next_open",
            "notional": 4_000.0,
            "candidate": {"ticker": "WIN", "date": as_of},
            "trade_enabled": False,
        }
    )

    snapshot = build_sec_ftd_finra_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=stale_ohlcv,
        candidate_universe=["WIN"],
        ftd_rows=_ftd_rows(),
        finra_rows=_finra_rows(),
        state=state,
        persist=False,
        config={"allow_network_fetch": False},
    )

    assert snapshot["filled_count"] == 0
    assert snapshot["pending_count"] == 0
    assert snapshot["skipped_entries_today"][0]["status"] == "skipped_missing_next_open"
    assert snapshot["open_position_count"] == 0


def test_non_session_returns_neutral_skip_before_spy_asof_check():
    snapshot = build_sec_ftd_finra_paper_sleeve_snapshot(
        as_of="2026-06-20",
        ohlcv_by_ticker={},
        candidate_universe=["WIN"],
        ftd_rows=[],
        finra_rows=[],
        state=empty_sec_ftd_finra_paper_state(),
        persist=False,
        config={"allow_network_fetch": False},
    )

    assert snapshot["error"] == "non_us_equity_session"
    assert snapshot["data_source"]["status"] == "non_us_equity_session"


def test_default_off_alpha_attribution_includes_sec_ftd_finra_surface():
    report = build_default_off_alpha_attribution_report(
        as_of="2026-03-02",
        sec_ftd_finra_paper_sleeve={
            "sleeve": "SEC_FTD_FINRA_CONFIRMED_PAPER",
            "candidate_count": 1,
            "pending_count": 1,
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["min_closed_trades"],
                "metrics": {"closed_trades": 0, "realized_pnl": 0.0},
            },
            "data_source": {"sec_ftd_row_count": 2, "finra_row_count": 2},
            "ftd_pressure": {"candidate_count": 1},
            "finra_confirmation": {
                "admitted_candidate_count": 1,
                "rejected_count": 1,
            },
        },
    )

    surfaces = {row["name"]: row for row in report["surfaces"]}
    assert "sec_ftd_finra_confirmed" in surfaces
    assert surfaces["sec_ftd_finra_confirmed"]["status"] == "blocked"
    assert surfaces["sec_ftd_finra_confirmed"]["extra_metrics"]["sec_ftd_rows"] == 2
    assert surfaces["sec_ftd_finra_confirmed"]["extra_metrics"]["finra_rows"] == 2
    assert surfaces["sec_ftd_finra_confirmed"]["extra_metrics"]["finra_confirmed"] == 1
