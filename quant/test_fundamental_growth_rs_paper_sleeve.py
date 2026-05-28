from __future__ import annotations

from datetime import date, timedelta

from quant.default_off_alpha_attribution import build_default_off_alpha_attribution_report
from quant.fundamental_growth_rs_paper_sleeve import (
    FILING_RECENCY_RULE_VERSION,
    GOVERNOR_RULE_VERSION,
    LOW_VOLUME_PARTICIPATION_RULE_VERSION,
    REPLACEMENT_VALUE_RULE_VERSION,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_fundamental_growth_rs_paper_sleeve_snapshot,
    build_fundamental_growth_rs_replacement_value_report,
    empty_fundamental_growth_rs_paper_state,
)


def _rows(
    *,
    base: float,
    step: float,
    days: int = 132,
    volume: float = 2_000_000.0,
) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(days):
        close = base + step * idx
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": round(close * 0.998, 4),
                "high": round(close * 1.01, 4),
                "low": round(close * 0.99, 4),
                "close": round(close, 4),
                "volume": volume,
            }
        )
    return rows


def _fact(
    ticker: str,
    canonical: str,
    fy: int,
    fp: str,
    filed: str,
    value: float,
) -> dict:
    return {
        "ticker": ticker,
        "canonical": canonical,
        "fy": fy,
        "fp": fp,
        "filed": filed,
        "end": f"{fy}-03-31",
        "form": "10-Q",
        "value": value,
        "duration_days": 91,
    }


def _facts() -> list[dict]:
    return [
        _fact("AMD", "eps_diluted", 2025, "Q1", "2025-04-25", 1.00),
        _fact("AMD", "eps_diluted", 2026, "Q1", "2026-04-25", 1.45),
        _fact("AMD", "revenue", 2025, "Q1", "2025-04-25", 1000.0),
        _fact("AMD", "revenue", 2026, "Q1", "2026-04-25", 1260.0),
        _fact("AMD", "operating_income", 2026, "Q1", "2026-04-25", 220.0),
    ]


def _ohlcv() -> dict[str, list[dict]]:
    return {
        "SPY": _rows(base=100.0, step=0.04, volume=20_000_000.0),
        "AMD": _rows(base=80.0, step=0.34, volume=1_500_000.0),
        "AAPL": _rows(base=170.0, step=0.02, volume=1_000_000.0),
    }


def test_snapshot_adds_top1_companyfacts_growth_rs_candidate_without_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][125]["date"]

    snapshot = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=_facts(),
        candidate_universe=["AMD", "AAPL"],
        state=empty_fundamental_growth_rs_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["pending_count"] == 1
    assert snapshot["new_pending_entries"][0]["ticker"] == "AMD"
    assert snapshot["candidates"][0]["rule_version"] == RULE_VERSION
    assert snapshot["candidates"][0]["source_rule_version"] == SOURCE_RULE_VERSION
    assert snapshot["candidates"][0]["governor_rule_version"] == GOVERNOR_RULE_VERSION
    assert snapshot["candidates"][0]["low_volume_participation_rule_version"] == LOW_VOLUME_PARTICIPATION_RULE_VERSION
    assert snapshot["candidates"][0]["filing_recency_rule_version"] == FILING_RECENCY_RULE_VERSION
    assert snapshot["candidates"][0]["fundamental_growth_points_v1"] == 2
    assert snapshot["candidates"][0]["operating_profit_quality_pass_v1"] is True
    assert snapshot["candidates"][0]["rs_proxy_score_v1"] >= 0.75
    assert snapshot["candidates"][0]["filing_recency_pass_v1"] is True
    assert snapshot["candidates"][0]["intended_notional"] == 10_500.0
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False


def test_low_volume_participation_support_scales_paper_notional_without_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][125]["date"]
    ohlcv["AMD"][125]["volume"] = 500_000.0

    snapshot = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=_facts(),
        candidate_universe=["AMD", "AAPL"],
        state=empty_fundamental_growth_rs_paper_state(),
        persist=False,
    )

    candidate = snapshot["candidates"][0]
    assert candidate["low_volume_participation_pass_v1"] is True
    assert candidate["low_volume_ratio_20_max"] == 0.9
    assert candidate["low_volume_notional_scalar"] == 1.1
    assert candidate["filing_recency_pass_v1"] is True
    assert candidate["filing_recency_notional_scalar"] == 1.05
    assert candidate["closed_ledger_notional_scalar"] == 1.155
    assert candidate["intended_notional"] == 11_550.0
    assert snapshot["low_volume_participation"]["supported_candidate_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False


def test_filing_recency_support_scales_paper_notional_without_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][125]["date"]

    snapshot = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=_facts(),
        candidate_universe=["AMD", "AAPL"],
        state=empty_fundamental_growth_rs_paper_state(),
        persist=False,
    )

    candidate = snapshot["candidates"][0]
    assert candidate["filing_recency_rule_version"] == FILING_RECENCY_RULE_VERSION
    assert candidate["operating_income_filing_age_days"] <= 90
    assert candidate["filing_recency_max_days"] == 90
    assert candidate["filing_recency_pass_v1"] is True
    assert candidate["filing_recency_notional_scalar"] == 1.05
    assert candidate["closed_ledger_notional_scalar"] == 1.05
    assert candidate["intended_notional"] == 10_500.0
    assert snapshot["filing_recency"]["supported_candidate_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False


def test_closed_ledger_governor_scales_same_ticker_profit_and_global_drawdown():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][125]["date"]
    state = empty_fundamental_growth_rs_paper_state()
    state["closed_positions"] = [
        {"ticker": "AMD", "pnl": 10_000.0},
        {"ticker": "LOSS", "pnl": -18_000.0},
    ]

    snapshot = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=_facts(),
        candidate_universe=["AMD", "AAPL"],
        state=state,
        persist=False,
    )

    candidate = snapshot["candidates"][0]
    assert snapshot["closed_ledger_governor"]["global_drawdown_scalar"] == 0.25
    assert candidate["ticker_profit_cap_scalar"] == 0.05
    assert candidate["global_drawdown_scalar"] == 0.25
    assert candidate["filing_recency_pass_v1"] is True
    assert candidate["closed_ledger_notional_scalar"] == 0.013125
    assert candidate["intended_notional"] == 131.25


def test_snapshot_fills_next_session_and_closes_after_fixed_hold_without_orders():
    ohlcv = _ohlcv()
    first = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=ohlcv["SPY"][125]["date"],
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=_facts(),
        candidate_universe=["AMD", "AAPL"],
        state=empty_fundamental_growth_rs_paper_state(),
        persist=False,
    )

    state = empty_fundamental_growth_rs_paper_state()
    state["pending_entries"] = first["pending_entries"]
    second = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=ohlcv["SPY"][126]["date"],
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=_facts(),
        candidate_universe=["AMD", "AAPL"],
        state=state,
        open_prices={"AMD": ohlcv["AMD"][126]["open"]},
        current_prices={"AMD": ohlcv["AMD"][126]["close"]},
        persist=False,
    )
    assert second["filled_count"] == 1
    assert second["open_position_count"] == 1
    assert second["trade_enabled"] is False

    close_state = empty_fundamental_growth_rs_paper_state()
    close_state["open_positions"] = second["open_positions"]
    close_state["open_positions"][0]["observed_trading_days"] = 9
    third = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=ohlcv["SPY"][131]["date"],
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=_facts(),
        candidate_universe=[],
        state=close_state,
        current_prices={"AMD": ohlcv["AMD"][131]["close"]},
        persist=False,
    )

    assert third["closed_count_today"] == 1
    assert third["closed_positions_today"][0]["exit_reason"] == "max_hold_days"
    assert third["realized_pnl_to_date"] > 0
    assert third["replacement_value_report"]["rule_version"] == REPLACEMENT_VALUE_RULE_VERSION
    assert third["production_impact"]["alters_orders"] is False


def test_replacement_value_report_tracks_concentration_and_read_only_boundary():
    report = build_fundamental_growth_rs_replacement_value_report(
        candidates=[{"ticker": "AMD"}],
        pending_entries=[{"ticker": "AMD"}],
        open_positions=[{"ticker": "OPEN", "unrealized_pnl": 125.5}],
        closed_positions=[
            {"ticker": "AMD", "pnl": 200.0},
            {"ticker": "LOSS", "pnl": -50.0},
        ],
        skipped_entries=[{"ticker": "SKIP"}],
    )

    assert report["read_only"] is True
    assert report["closed_count"] == 2
    assert report["closed_pnl"] == 150.0
    assert report["positive_closed_pnl"] == 200.0
    assert report["by_ticker"]["AMD"]["positive_pnl_share"] == 1.0
    assert report["trade_enabled"] is False
    assert report["alters_orders"] is False


def test_default_off_alpha_report_surfaces_fundamental_growth_rs_sleeve():
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
        "source_rule_version": SOURCE_RULE_VERSION,
        "governor_rule_version": GOVERNOR_RULE_VERSION,
    }

    report = build_default_off_alpha_attribution_report(
        as_of="2026-05-28",
        fundamental_growth_rs_paper_sleeve=sleeve,
    )

    surfaces = {row["name"]: row for row in report["surfaces"]}
    assert "fundamental_growth_rs" in surfaces
    assert surfaces["fundamental_growth_rs"]["label"] == "FUNDAMENTAL_GROWTH_RS_PAPER"
    assert surfaces["fundamental_growth_rs"]["trade_enabled"] is False
    assert "min_closed_trades" in surfaces["fundamental_growth_rs"]["blockers"]
