from __future__ import annotations

from datetime import date, timedelta

from quant.volatility_contraction_paper_sleeve import (
    MARKET_CONFIRMATION_RULE_VERSION,
    POCKET_PIVOT_CONTEXT_RULE_VERSION,
    REPLACEMENT_VALUE_RULE_VERSION,
    RULE_VERSION,
    build_qqq_spy_market_confirmation,
    build_volatility_contraction_paper_sleeve_snapshot,
    build_volatility_contraction_replacement_value_report,
    compute_pre_signal_pocket_pivot_context,
    empty_volatility_contraction_paper_state,
)


def _market_rows(start_price: float, step: float, *, days: int = 80) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(days):
        close = start_price + step * idx
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": round(close * 0.995, 4),
                "high": round(close * 1.01, 4),
                "low": round(close * 0.99, 4),
                "close": round(close, 4),
                "volume": 10_000_000,
            }
        )
    return rows


def _volatility_contraction_rows(*, days: int = 80) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(days):
        if idx < 50:
            close = 50.0 + idx * 0.05
            high = close + 1.0
            low = close - 1.0
        elif idx < 60:
            close = 52.0 + (idx - 50) * 0.02
            high = close + 0.08
            low = close - 0.08
        elif idx == 60:
            close = 54.0
            high = 54.10
            low = 53.75
        else:
            close = 54.0 + (idx - 60) * 0.25
            high = close + 0.20
            low = close - 0.20
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": round(close * 1.001, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(close, 4),
                "volume": 1_200_000,
            }
        )
    return rows


def _pocket_rows(
    closes: list[float],
    volumes: list[float],
    *,
    start: date = date(2026, 1, 1),
) -> list[dict]:
    rows = []
    for idx, (close, volume) in enumerate(zip(closes, volumes)):
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": volume,
            }
        )
    return rows


def test_qqq_spy_market_confirmation_uses_same_close_to_close_field():
    spy_rows = _market_rows(100.0, 0.05)
    qqq_rows = _market_rows(100.0, 0.25)
    as_of = spy_rows[60]["date"]

    market = build_qqq_spy_market_confirmation(
        {"SPY": spy_rows, "QQQ": qqq_rows},
        as_of=as_of,
    )

    assert market["rule_version"] == MARKET_CONFIRMATION_RULE_VERSION
    assert market["passed"] is True
    assert market["qqq_return_20d"] > market["spy_return_20d"]
    assert market["trade_enabled"] is False
    assert market["alters_orders"] is False


def test_snapshot_adds_top1_candidate_only_when_qqq_leads_spy():
    spy_rows = _market_rows(100.0, 0.05)
    qqq_rows = _market_rows(100.0, 0.25)
    nvda_rows = _volatility_contraction_rows()
    as_of = nvda_rows[60]["date"]

    snapshot = build_volatility_contraction_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={"SPY": spy_rows, "QQQ": qqq_rows, "NVDA": nvda_rows},
        candidate_universe=["NVDA"],
        state=empty_volatility_contraction_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["pending_count"] == 1
    assert snapshot["market_confirmation"]["passed"] is True
    assert snapshot["candidates"][0]["rule_version"] == RULE_VERSION
    assert snapshot["candidates"][0]["market_confirmation"]["passed"] is True
    assert snapshot["candidates"][0]["intended_notional"] == 10_000.0
    assert snapshot["candidates"][0]["pocket_pivot_context_rule_version"] == (
        POCKET_PIVOT_CONTEXT_RULE_VERSION
    )
    assert "pre_signal_pocket_pivot_seen_10d" in snapshot["candidates"][0]
    assert snapshot["candidates"][0]["alters_orders"] is False
    assert snapshot["production_impact"]["alters_orders"] is False
    assert snapshot["trade_enabled"] is False


def test_snapshot_rejects_candidate_when_qqq_lags_spy():
    spy_rows = _market_rows(100.0, 0.25)
    qqq_rows = _market_rows(100.0, 0.05)
    nvda_rows = _volatility_contraction_rows()
    as_of = nvda_rows[60]["date"]

    snapshot = build_volatility_contraction_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={"SPY": spy_rows, "QQQ": qqq_rows, "NVDA": nvda_rows},
        candidate_universe=["NVDA"],
        state=empty_volatility_contraction_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["rejected_candidate_count"] == 1
    assert snapshot["market_confirmation"]["passed"] is False
    assert "qqq_spy_confirmation_failed" in snapshot["rejected_candidates"][0]["reasons"]
    assert snapshot["production_impact"]["trade_enabled"] is False


def test_snapshot_fills_next_session_and_closes_after_fixed_hold_without_orders():
    spy_rows = _market_rows(100.0, 0.05)
    qqq_rows = _market_rows(100.0, 0.25)
    nvda_rows = _volatility_contraction_rows()
    first = build_volatility_contraction_paper_sleeve_snapshot(
        as_of=nvda_rows[60]["date"],
        ohlcv_by_ticker={"SPY": spy_rows, "QQQ": qqq_rows, "NVDA": nvda_rows},
        candidate_universe=["NVDA"],
        state=empty_volatility_contraction_paper_state(),
        persist=False,
    )

    state = empty_volatility_contraction_paper_state()
    state["pending_entries"] = first["pending_entries"]
    second = build_volatility_contraction_paper_sleeve_snapshot(
        as_of=nvda_rows[61]["date"],
        ohlcv_by_ticker={"SPY": spy_rows, "QQQ": qqq_rows, "NVDA": nvda_rows},
        candidate_universe=["NVDA"],
        state=state,
        persist=False,
    )
    assert second["filled_count"] == 1
    assert second["open_position_count"] == 1
    assert second["trade_enabled"] is False

    close_state = empty_volatility_contraction_paper_state()
    close_state["open_positions"] = second["open_positions"]
    close_state["open_positions"][0]["observed_trading_days"] = 9
    third = build_volatility_contraction_paper_sleeve_snapshot(
        as_of=nvda_rows[70]["date"],
        ohlcv_by_ticker={"SPY": spy_rows, "QQQ": qqq_rows, "NVDA": nvda_rows},
        candidate_universe=[],
        state=close_state,
        persist=False,
    )

    assert third["closed_count_today"] == 1
    assert third["closed_positions_today"][0]["exit_reason"] == "max_hold_days"
    assert third["realized_pnl_to_date"] > 0
    assert third["replacement_value_report"]["rule_version"] == REPLACEMENT_VALUE_RULE_VERSION
    assert third["production_impact"]["production_orders_changed"] is False


def test_replacement_value_report_tracks_cash_slot_and_concentration():
    report = build_volatility_contraction_replacement_value_report(
        candidates=[{"ticker": "NVDA"}],
        pending_entries=[{"ticker": "NVDA"}],
        open_positions=[{"ticker": "MSFT", "unrealized_pnl": 125.5}],
        closed_positions=[
            {"ticker": "NVDA", "pnl": 200.0},
            {"ticker": "LOSS", "pnl": -50.0},
        ],
        skipped_entries=[{"ticker": "SKIP"}],
    )

    assert report["read_only"] is True
    assert report["closed_count"] == 2
    assert report["closed_pnl"] == 150.0
    assert report["positive_closed_pnl"] == 200.0
    assert report["by_ticker"]["NVDA"]["positive_pnl_share"] == 1.0
    assert report["trade_enabled"] is False
    assert report["alters_orders"] is False


def test_pre_signal_pocket_pivot_passes_when_up_volume_beats_prior_down_volume():
    rows = _pocket_rows(
        [100, 99, 98, 99, 98, 99, 98, 99, 98, 99, 98, 99, 100, 100.5, 101],
        [90, 80, 100, 90, 110, 100, 95, 105, 100, 90, 95, 100, 111, 90, 90],
    )

    context = compute_pre_signal_pocket_pivot_context(rows, rows[14]["date"])

    assert context["pre_signal_pocket_pivot_seen_10d"] is True
    assert context["pre_signal_pocket_pivot_count_10d"] == 1
    assert context["latest_pre_signal_pocket_pivot_date"] == rows[12]["date"]
    assert context["latest_pre_signal_pocket_pivot_volume_ratio"] == 1.009091
    assert context["pocket_pivot_context_status"] == "available"
    assert context["trade_enabled"] is False
    assert context["alters_orders"] is False


def test_pre_signal_pocket_pivot_equal_volume_does_not_pass():
    rows = _pocket_rows(
        [100, 99, 98, 99, 98, 99, 98, 99, 98, 99, 98, 99, 100, 100.5, 101],
        [90, 80, 100, 90, 110, 100, 95, 105, 100, 90, 95, 100, 110, 90, 90],
    )

    context = compute_pre_signal_pocket_pivot_context(rows, rows[14]["date"])

    assert context["pre_signal_pocket_pivot_seen_10d"] is False
    assert context["pre_signal_pocket_pivot_count_10d"] == 0
    assert context["latest_pre_signal_pocket_pivot_date"] is None
    assert context["pocket_pivot_context_status"] == "available"


def test_pre_signal_pocket_pivot_excludes_signal_date():
    rows = _pocket_rows(
        [100, 99, 98, 99, 98, 99, 98, 99, 98, 99, 98, 99, 100, 100.5, 105],
        [90, 80, 100, 90, 110, 100, 95, 105, 100, 90, 95, 100, 110, 90, 1000],
    )

    context = compute_pre_signal_pocket_pivot_context(rows, rows[14]["date"])

    assert context["pre_signal_pocket_pivot_seen_10d"] is False
    assert context["latest_pre_signal_pocket_pivot_date"] is None


def test_pre_signal_pocket_pivot_missing_down_day_volume_is_unavailable_false():
    rows = _pocket_rows(
        [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
        [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
    )

    context = compute_pre_signal_pocket_pivot_context(rows, rows[11]["date"])

    assert context["pre_signal_pocket_pivot_seen_10d"] is False
    assert context["pre_signal_pocket_pivot_count_10d"] == 0
    assert context["pocket_pivot_context_status"] == "no_prior_down_volume"


def test_pre_signal_pocket_pivot_does_not_inspect_future_rows():
    rows = _pocket_rows(
        [100, 99, 98, 99, 98, 99, 98, 99, 98, 99, 98, 99, 100, 101, 102, 104],
        [90, 80, 100, 90, 110, 100, 95, 105, 100, 90, 95, 100, 110, 90, 1000, 1200],
    )

    context = compute_pre_signal_pocket_pivot_context(rows, rows[13]["date"])

    assert context["pre_signal_pocket_pivot_seen_10d"] is False
    assert context["latest_pre_signal_pocket_pivot_date"] is None
