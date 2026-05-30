from __future__ import annotations

from datetime import date, timedelta

from quant.default_off_alpha_attribution import build_default_off_alpha_attribution_report
from quant.finra_iwm_paper_sleeve import (
    COOLDOWN_RULE_VERSION,
    MARKET_CONFIRMATION_RULE_VERSION,
    RULE_VERSION,
    build_finra_iwm_paper_sleeve_snapshot,
    empty_finra_iwm_paper_state,
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
        "IWM": _rows(base=100.0, step=0.20),
        "WIN": _rows(
            base=80.0,
            step=0.08,
            breakout_day=asof_idx,
            breakout_close=102.0,
            spike_day=asof_idx,
            spike_volume=2_500_000.0,
        ),
        "LOW": _rows(base=40.0, step=0.03),
        "MID": _rows(base=45.0, step=0.04),
    }
    win_close = rows["WIN"][asof_idx]["close"]
    rows["WIN"][asof_idx]["high"] = round(win_close * 1.001, 4)
    rows["WIN"][asof_idx]["low"] = round(win_close * 0.97, 4)
    return rows


def _finra_rows() -> list[dict]:
    return [
        {
            "ticker": "WIN",
            "settlement_date": "2026-02-13",
            "publication_date": "2026-02-25",
            "days_to_cover": 10.0,
            "short_interest_change_pct": 50.0,
            "short_interest": 1_000_000,
            "previous_short_interest": 500_000,
        },
        {
            "ticker": "LOW",
            "settlement_date": "2026-02-13",
            "publication_date": "2026-02-25",
            "days_to_cover": 1.0,
            "short_interest_change_pct": 0.0,
            "short_interest": 100_000,
            "previous_short_interest": 100_000,
        },
        {
            "ticker": "MID",
            "settlement_date": "2026-02-13",
            "publication_date": "2026-02-25",
            "days_to_cover": 2.0,
            "short_interest_change_pct": 10.0,
            "short_interest": 200_000,
            "previous_short_interest": 180_000,
        },
    ]


def test_finra_iwm_snapshot_admits_top_candidate_without_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][60]["date"]

    snapshot = build_finra_iwm_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["WIN", "LOW", "MID"],
        finra_rows=_finra_rows(),
        state=empty_finra_iwm_paper_state(),
        persist=False,
        config={"allow_network_fetch": False},
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False
    assert snapshot["market_confirmation"]["rule_version"] == MARKET_CONFIRMATION_RULE_VERSION
    assert snapshot["market_confirmation"]["passed"] is True
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "WIN"
    assert candidate["rule_version"] == RULE_VERSION
    assert candidate["finra_short_pressure_score"] >= 0.70
    assert candidate["same_ticker_cooldown_rule_version"] == COOLDOWN_RULE_VERSION
    assert candidate["trade_enabled"] is False
    assert candidate["alters_orders"] is False


def test_same_ticker_cooldown_blocks_recent_admitted_candidate():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][60]["date"]
    state = empty_finra_iwm_paper_state()
    state["closed_positions"].append(
        {
            "ticker": "WIN",
            "created_asof": (date.fromisoformat(as_of) - timedelta(days=3)).isoformat(),
            "pnl": 100.0,
        }
    )

    snapshot = build_finra_iwm_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["WIN", "LOW", "MID"],
        finra_rows=_finra_rows(),
        state=state,
        persist=False,
        config={"allow_network_fetch": False},
    )

    assert snapshot["raw_candidate_count"] == 1
    assert snapshot["candidate_count"] == 0
    assert snapshot["same_ticker_cooldown"]["rejected_count"] == 1
    assert snapshot["new_pending_count"] == 0


def test_stale_missing_asof_price_does_not_fill_pending_entry():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][60]["date"]
    stale_ohlcv = dict(ohlcv)
    stale_ohlcv["WIN"] = [row for row in ohlcv["WIN"] if row["date"] != as_of]
    state = empty_finra_iwm_paper_state()
    state["pending_entries"].append(
        {
            "decision_id": "test",
            "sleeve": "FINRA_IWM_CONFIRMED_PAPER",
            "ticker": "WIN",
            "created_asof": (date.fromisoformat(as_of) - timedelta(days=1)).isoformat(),
            "status": "pending_next_open",
            "notional": 10_000.0,
            "candidate": {"ticker": "WIN", "date": as_of},
            "trade_enabled": False,
        }
    )

    snapshot = build_finra_iwm_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=stale_ohlcv,
        candidate_universe=["WIN", "LOW", "MID"],
        finra_rows=_finra_rows(),
        state=state,
        persist=False,
        config={"allow_network_fetch": False},
    )

    assert snapshot["filled_count"] == 0
    assert snapshot["pending_count"] == 0
    assert snapshot["skipped_entries_today"][0]["status"] == "skipped_missing_next_open"
    assert snapshot["open_position_count"] == 0


def test_default_off_alpha_attribution_includes_finra_iwm_surface():
    report = build_default_off_alpha_attribution_report(
        as_of="2026-03-02",
        finra_iwm_paper_sleeve={
            "sleeve": "FINRA_IWM_CONFIRMED_PAPER",
            "candidate_count": 1,
            "pending_count": 1,
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["min_closed_trades"],
                "metrics": {"closed_trades": 0, "realized_pnl": 0.0},
            },
            "data_source": {"row_count": 3},
            "same_ticker_cooldown": {"rejected_count": 0},
        },
    )

    surfaces = {row["name"]: row for row in report["surfaces"]}
    assert "finra_iwm_confirmed" in surfaces
    assert surfaces["finra_iwm_confirmed"]["status"] == "blocked"
    assert surfaces["finra_iwm_confirmed"]["extra_metrics"]["finra_rows"] == 3
