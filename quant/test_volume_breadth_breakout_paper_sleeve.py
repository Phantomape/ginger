from __future__ import annotations

from datetime import date, timedelta

from quant.volume_breadth_breakout_paper_sleeve import (
    BREADTH_INTENSITY_RULE_VERSION,
    BREADTH_RULE_VERSION,
    REPLACEMENT_VALUE_RULE_VERSION,
    RULE_VERSION,
    build_volume_breadth_breakout_paper_sleeve_snapshot,
    build_volume_breadth_breakout_replacement_value_report,
    build_volume_breadth_context,
    empty_volume_breadth_breakout_paper_state,
)
from quant.default_off_alpha_attribution import build_default_off_alpha_attribution_report


def _rows(
    *,
    base: float = 50.0,
    step: float = 0.12,
    days: int = 72,
    breakout_day: int | None = None,
    breakout_close: float | None = None,
    spike_day: int | None = None,
    spike_volume: float = 2_000_000,
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


def _breadth_universe(asof_idx: int = 60) -> dict[str, list[dict]]:
    rows = {"SPY": _rows(base=100.0, step=0.05)}
    rows["WIN"] = _rows(
        base=80.0,
        step=0.08,
        breakout_day=asof_idx,
        breakout_close=102.0,
        spike_day=asof_idx,
        spike_volume=2_500_000,
    )
    for idx in range(34):
        ticker = f"B{idx:02d}"
        spike = asof_idx if idx < 5 else None
        rows[ticker] = _rows(
            base=40.0 + idx,
            step=0.07,
            spike_day=spike,
            spike_volume=2_000_000,
        )
    return rows


def test_volume_breadth_context_passes_on_broad_up_volume_thrust():
    ohlcv = _breadth_universe()
    as_of = ohlcv["SPY"][60]["date"]

    context = build_volume_breadth_context(
        ohlcv,
        as_of=as_of,
        candidate_universe=list(ohlcv),
    )

    assert context["rule_version"] == BREADTH_RULE_VERSION
    assert context["passed"] is True
    assert context["eligible_ticker_count"] >= 30
    assert context["volume_breadth_fraction"] >= 0.12
    assert context["market_up_fraction"] >= 0.52
    assert context["above_50d_fraction"] >= 0.45
    assert context["trade_enabled"] is False
    assert context["alters_orders"] is False


def test_snapshot_adds_top1_breakout_only_when_breadth_passes():
    ohlcv = _breadth_universe()
    as_of = ohlcv["SPY"][60]["date"]

    snapshot = build_volume_breadth_breakout_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(ohlcv),
        state=empty_volume_breadth_breakout_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] >= 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["pending_count"] == 1
    assert snapshot["volume_breadth_context"]["passed"] is True
    assert snapshot["new_pending_entries"][0]["ticker"] == "WIN"
    assert snapshot["candidates"][0]["rule_version"] == RULE_VERSION
    assert snapshot["candidates"][0]["volume_breadth_rule_version"] == BREADTH_RULE_VERSION
    assert snapshot["candidates"][0]["intended_notional"] == 10_000.0
    assert snapshot["candidates"][0]["alters_orders"] is False
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False


def test_breadth_intensity_support_scales_paper_notional_without_orders():
    ohlcv = _breadth_universe()
    as_of_idx = 60
    as_of = ohlcv["SPY"][as_of_idx]["date"]
    for idx in range(5, 13):
        ohlcv[f"B{idx:02d}"][as_of_idx]["volume"] = 2_000_000.0

    snapshot = build_volume_breadth_breakout_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(ohlcv),
        state=empty_volume_breadth_breakout_paper_state(),
        persist=False,
    )

    candidate = snapshot["candidates"][0]
    assert snapshot["volume_breadth_context"]["volume_breadth_fraction"] >= 0.25
    assert snapshot["breadth_intensity_support"]["rule_version"] == BREADTH_INTENSITY_RULE_VERSION
    assert snapshot["breadth_intensity_support"]["supported_candidate_count"] >= 1
    assert candidate["breadth_intensity_support_rule_version"] == BREADTH_INTENSITY_RULE_VERSION
    assert candidate["breadth_intensity_support_pass_v1"] is True
    assert candidate["breadth_intensity_notional_scalar"] == 1.1
    assert candidate["base_paper_notional_usd"] == 10_000.0
    assert candidate["intended_notional"] == 11_000.0
    assert candidate["breadth_intensity_trade_enabled"] is False
    assert candidate["breadth_intensity_alters_orders"] is False
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False


def test_snapshot_rejects_breakout_when_breadth_is_too_thin():
    ohlcv = {
        "SPY": _rows(base=100.0, step=0.05),
        "WIN": _rows(
            base=80.0,
            step=0.08,
            breakout_day=60,
            breakout_close=102.0,
            spike_day=60,
            spike_volume=2_500_000,
        ),
    }
    as_of = ohlcv["SPY"][60]["date"]

    snapshot = build_volume_breadth_breakout_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(ohlcv),
        state=empty_volume_breadth_breakout_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["rejected_candidate_count"] == 1
    assert snapshot["volume_breadth_context"]["passed"] is False
    assert "volume_breadth_thrust_failed" in snapshot["rejected_candidates"][0]["reasons"]
    assert snapshot["production_impact"]["trade_enabled"] is False


def test_snapshot_fills_next_session_and_closes_after_fixed_hold_without_orders():
    ohlcv = _breadth_universe()
    first = build_volume_breadth_breakout_paper_sleeve_snapshot(
        as_of=ohlcv["SPY"][60]["date"],
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(ohlcv),
        state=empty_volume_breadth_breakout_paper_state(),
        persist=False,
    )

    state = empty_volume_breadth_breakout_paper_state()
    state["pending_entries"] = first["pending_entries"]
    second = build_volume_breadth_breakout_paper_sleeve_snapshot(
        as_of=ohlcv["SPY"][61]["date"],
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(ohlcv),
        state=state,
        persist=False,
    )
    assert second["filled_count"] == 1
    assert second["open_position_count"] == 1
    assert second["trade_enabled"] is False

    close_state = empty_volume_breadth_breakout_paper_state()
    close_state["open_positions"] = second["open_positions"]
    close_state["open_positions"][0]["observed_trading_days"] = 9
    third = build_volume_breadth_breakout_paper_sleeve_snapshot(
        as_of=ohlcv["SPY"][70]["date"],
        ohlcv_by_ticker=ohlcv,
        candidate_universe=[],
        state=close_state,
        persist=False,
    )

    assert third["closed_count_today"] == 1
    assert third["closed_positions_today"][0]["exit_reason"] == "max_hold_days"
    assert third["realized_pnl_to_date"] > 0
    assert third["replacement_value_report"]["rule_version"] == REPLACEMENT_VALUE_RULE_VERSION
    assert third["production_impact"]["alters_orders"] is False


def test_replacement_value_report_tracks_cash_slot_and_concentration():
    report = build_volume_breadth_breakout_replacement_value_report(
        candidates=[{"ticker": "WIN"}],
        pending_entries=[{"ticker": "WIN"}],
        open_positions=[{"ticker": "OPEN", "unrealized_pnl": 125.5}],
        closed_positions=[
            {"ticker": "WIN", "pnl": 200.0},
            {"ticker": "LOSS", "pnl": -50.0},
        ],
        skipped_entries=[{"ticker": "SKIP"}],
    )

    assert report["read_only"] is True
    assert report["closed_count"] == 2
    assert report["closed_pnl"] == 150.0
    assert report["positive_closed_pnl"] == 200.0
    assert report["by_ticker"]["WIN"]["positive_pnl_share"] == 1.0
    assert report["trade_enabled"] is False
    assert report["alters_orders"] is False


def test_default_off_alpha_report_surfaces_volume_breadth_sleeve():
    sleeve = {
        "candidate_count": 1,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_count_today": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "trade_enabled": False,
        "forward_paper_gate": {
            "passed": False,
            "status": "blocked",
            "reasons": ["min_closed_trades"],
            "metrics": {"closed_trades": 0},
        },
    }

    report = build_default_off_alpha_attribution_report(
        as_of="2026-05-26",
        volume_breadth_breakout_paper_sleeve=sleeve,
    )

    surfaces = {row["name"]: row for row in report["surfaces"]}
    assert "volume_breadth_breakout" in surfaces
    assert surfaces["volume_breadth_breakout"]["label"] == "VOLUME_BREADTH_BREAKOUT_PAPER"
    assert surfaces["volume_breadth_breakout"]["trade_enabled"] is False
    assert surfaces["volume_breadth_breakout"]["extra_metrics"]["breadth_intensity_supported"] is None
    assert "min_closed_trades" in surfaces["volume_breadth_breakout"]["blockers"]
