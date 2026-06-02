from __future__ import annotations

from datetime import date, timedelta

from quant.default_off_alpha_attribution import build_default_off_alpha_attribution_report
from quant.post_earnings_underpriced_drift_paper_sleeve import (
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_post_earnings_underpriced_drift_paper_sleeve_snapshot,
    empty_post_earnings_underpriced_drift_paper_state,
)


def _rows(
    *,
    base: float,
    step: float,
    days: int = 80,
    jump_day: int | None = None,
    jump_close: float | None = None,
) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(days):
        close = base + step * idx
        if jump_day is not None and idx >= jump_day:
            close = (jump_close if jump_close is not None else close * 1.20) + 0.25 * (idx - jump_day)
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": round(close * 0.995, 4),
                "high": round(close * 1.005, 4),
                "low": round(close * 0.97, 4),
                "close": round(close, 4),
                "volume": 1_000_000.0,
            }
        )
    return rows


def _ohlcv(event_idx: int = 55, signal_idx: int = 56) -> dict[str, list[dict]]:
    rows = {
        "SPY": _rows(base=100.0, step=0.10),
        "WIN": _rows(base=50.0, step=0.03, jump_day=signal_idx, jump_close=76.0),
        "OUT": _rows(base=45.0, step=0.90, jump_day=signal_idx, jump_close=105.0),
    }
    for ticker in ("WIN", "OUT"):
        close = rows[ticker][signal_idx]["close"]
        rows[ticker][signal_idx]["high"] = round(close * 1.005, 4)
        rows[ticker][signal_idx]["low"] = round(close * 0.96, 4)
    assert rows["SPY"][event_idx]["date"] != rows["SPY"][signal_idx]["date"]
    return rows


def _earnings_index(event_date: str) -> dict[str, list[tuple[str, dict]]]:
    prev = {
        "days_to_earnings": 2,
        "eps_actual_last": 1.0,
        "historical_surprise_pct": [5.0, 6.0, 4.0, 5.0],
        "avg_historical_surprise_pct": 5.0,
    }
    current = {
        "days_to_earnings": 65,
        "eps_actual_last": 1.2,
        "historical_surprise_pct": [5.0, 6.0, 4.0, 8.0],
        "avg_historical_surprise_pct": 5.75,
    }
    prior_date = (date.fromisoformat(event_date) - timedelta(days=1)).isoformat()
    return {
        "WIN": [(prior_date, dict(prev)), (event_date, dict(current))],
        "OUT": [(prior_date, dict(prev)), (event_date, dict(current))],
    }


def test_post_earnings_underpriced_snapshot_admits_candidate_without_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][56]["date"]
    event_date = ohlcv["SPY"][55]["date"]

    snapshot = build_post_earnings_underpriced_drift_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["WIN", "OUT"],
        earnings_index=_earnings_index(event_date),
        state=empty_post_earnings_underpriced_drift_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False
    assert snapshot["production_impact"]["parity_rule"] == RULE_VERSION
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "WIN"
    assert candidate["rule_version"] == RULE_VERSION
    assert candidate["source_rule_version"] == SOURCE_RULE_VERSION
    assert candidate["pre_event_rs20_vs_spy"] <= 0.0
    assert candidate["pre_event_underpriced_positive_surprise"] is True
    assert candidate["post_earnings_positive_surprise_drift_score"] > 0.0
    assert candidate["trade_enabled"] is False
    assert candidate["alters_orders"] is False


def test_pre_event_outperformer_is_rejected_by_underpricing_gate():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][56]["date"]
    event_date = ohlcv["SPY"][55]["date"]

    snapshot = build_post_earnings_underpriced_drift_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["OUT"],
        earnings_index=_earnings_index(event_date),
        state=empty_post_earnings_underpriced_drift_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["candidate_reject_counts"]["pre_event_rs20_outperformed_spy"] == 1
    assert snapshot["new_pending_count"] == 0


def test_missing_exact_asof_open_does_not_fill_pending_entry():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][56]["date"]
    stale_ohlcv = dict(ohlcv)
    stale_ohlcv["WIN"] = [row for row in ohlcv["WIN"] if row["date"] != as_of]
    state = empty_post_earnings_underpriced_drift_paper_state()
    state["pending_entries"].append(
        {
            "decision_id": "test",
            "sleeve": "POST_EARNINGS_UNDERPRICED_DRIFT_PAPER",
            "ticker": "WIN",
            "created_asof": (date.fromisoformat(as_of) - timedelta(days=1)).isoformat(),
            "status": "pending_next_open",
            "notional": 10_000.0,
            "candidate": {"ticker": "WIN", "date": as_of},
            "trade_enabled": False,
        }
    )

    snapshot = build_post_earnings_underpriced_drift_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=stale_ohlcv,
        candidate_universe=["WIN"],
        earnings_index=_earnings_index(ohlcv["SPY"][55]["date"]),
        state=state,
        persist=False,
    )

    assert snapshot["filled_count"] == 0
    assert snapshot["pending_count"] == 0
    assert snapshot["skipped_entries_today"][0]["status"] == "skipped_missing_next_open"
    assert snapshot["open_position_count"] == 0


def test_default_off_alpha_attribution_includes_post_earnings_surface():
    report = build_default_off_alpha_attribution_report(
        as_of="2026-03-02",
        post_earnings_underpriced_drift_paper_sleeve={
            "sleeve": "POST_EARNINGS_UNDERPRICED_DRIFT_PAPER",
            "source_rule_version": SOURCE_RULE_VERSION,
            "candidate_count": 1,
            "pending_count": 1,
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["min_closed_trades"],
                "metrics": {"closed_trades": 0, "realized_pnl": 0.0},
            },
            "candidate_audit": {"positive_surprise_event_count": 2},
            "earnings_snapshot_source": {"dates_loaded": 4},
            "candidate_reject_counts": {"pre_event_rs20_outperformed_spy": 1},
        },
    )

    surfaces = {row["name"]: row for row in report["surfaces"]}
    assert "post_earnings_underpriced_drift" in surfaces
    surface = surfaces["post_earnings_underpriced_drift"]
    assert surface["status"] == "blocked"
    assert surface["extra_metrics"]["source_rule_version"] == SOURCE_RULE_VERSION
    assert surface["extra_metrics"]["positive_surprise_events"] == 2
