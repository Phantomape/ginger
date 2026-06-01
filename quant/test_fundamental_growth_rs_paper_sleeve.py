from __future__ import annotations

from datetime import date, timedelta

from quant.default_off_alpha_attribution import build_default_off_alpha_attribution_report
from quant.fundamental_growth_rs_paper_sleeve import (
    FILING_RECENCY_RULE_VERSION,
    FILING_TIMELINESS_RULE_VERSION,
    GOVERNOR_RULE_VERSION,
    GROSS_MARGIN_QUALITY_RULE_VERSION,
    LOW_LIABILITY_RULE_VERSION,
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


def _trading_rows(
    *,
    base: float,
    step: float,
    days: int = 150,
    volume: float = 2_000_000.0,
) -> list[dict]:
    current = date(2026, 1, 1)
    rows = []
    while len(rows) < days:
        if current.weekday() < 5:
            idx = len(rows)
            close = base + step * idx
            rows.append(
                {
                    "date": current.isoformat(),
                    "open": round(close * 0.998, 4),
                    "high": round(close * 1.01, 4),
                    "low": round(close * 0.99, 4),
                    "close": round(close, 4),
                    "volume": volume,
                }
            )
        current += timedelta(days=1)
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
        _fact("AMD", "gross_profit", 2026, "Q1", "2026-04-25", 700.0),
        _fact("AMD", "operating_income", 2026, "Q1", "2026-04-25", 220.0),
        _fact("AMD", "assets", 2026, "Q1", "2026-04-25", 1000.0),
        _fact("AMD", "liabilities", 2026, "Q1", "2026-04-25", 500.0),
    ]


def _low_liability_facts() -> list[dict]:
    facts = [row for row in _facts() if row["canonical"] not in {"assets", "liabilities"}]
    facts.extend(
        [
            _fact("AMD", "assets", 2026, "Q1", "2026-04-25", 1000.0),
            _fact("AMD", "liabilities", 2026, "Q1", "2026-04-25", 250.0),
        ]
    )
    return facts


def _ohlcv() -> dict[str, list[dict]]:
    return {
        "SPY": _rows(base=100.0, step=0.04, volume=20_000_000.0),
        "AMD": _rows(base=80.0, step=0.34, volume=1_500_000.0),
        "AAPL": _rows(base=170.0, step=0.02, volume=1_000_000.0),
    }


def _trading_ohlcv() -> dict[str, list[dict]]:
    return {
        "SPY": _trading_rows(base=100.0, step=0.04, volume=20_000_000.0),
        "AMD": _trading_rows(base=80.0, step=0.34, volume=1_500_000.0),
        "AAPL": _trading_rows(base=170.0, step=0.02, volume=1_000_000.0),
    }


def _late_friday(rows: list[dict]) -> tuple[int, str]:
    for idx in range(125, len(rows)):
        value = date.fromisoformat(rows[idx]["date"])
        if value.weekday() == 4:
            return idx, value.isoformat()
    raise AssertionError("test fixture did not produce a late Friday")


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
    assert snapshot["candidates"][0]["gross_margin_rule_version"] == GROSS_MARGIN_QUALITY_RULE_VERSION
    assert snapshot["candidates"][0]["gross_margin_pass_v1"] is True
    assert snapshot["candidates"][0]["gross_margin"] > 0.4
    assert snapshot["candidates"][0]["low_volume_participation_rule_version"] == LOW_VOLUME_PARTICIPATION_RULE_VERSION
    assert snapshot["candidates"][0]["filing_recency_rule_version"] == FILING_RECENCY_RULE_VERSION
    assert snapshot["candidates"][0]["filing_timeliness_rule_version"] == FILING_TIMELINESS_RULE_VERSION
    assert snapshot["candidates"][0]["low_liability_rule_version"] == LOW_LIABILITY_RULE_VERSION
    assert snapshot["candidates"][0]["fundamental_growth_points_v1"] == 2
    assert snapshot["candidates"][0]["operating_profit_quality_pass_v1"] is True
    assert snapshot["candidates"][0]["rs_proxy_score_v1"] >= 0.75
    assert snapshot["candidates"][0]["filing_recency_pass_v1"] is True
    assert snapshot["candidates"][0]["filing_timeliness_pass_v1"] is True
    assert snapshot["candidates"][0]["low_liability_pass_v1"] is False
    assert snapshot["candidates"][0]["intended_notional"] == 11_025.0
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False


def test_gross_margin_quality_rejects_below_floor_without_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][125]["date"]
    facts = [
        row
        for row in _facts()
        if row["canonical"] != "gross_profit"
    ]
    facts.append(_fact("AMD", "gross_profit", 2026, "Q1", "2026-04-25", 300.0))

    snapshot = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=facts,
        candidate_universe=["AMD", "AAPL"],
        state=empty_fundamental_growth_rs_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["gross_margin_quality"]["rule_version"] == GROSS_MARGIN_QUALITY_RULE_VERSION
    assert snapshot["gross_margin_quality"]["min_gross_margin"] == 0.4
    assert snapshot["trade_enabled"] is False


def test_gross_margin_quality_uses_cost_of_revenue_fallback_without_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][125]["date"]
    facts = [
        row
        for row in _facts()
        if row["canonical"] != "gross_profit"
    ]
    facts.append(_fact("AMD", "cost_of_revenue", 2026, "Q1", "2026-04-25", 500.0))

    snapshot = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=facts,
        candidate_universe=["AMD", "AAPL"],
        state=empty_fundamental_growth_rs_paper_state(),
        persist=False,
    )

    candidate = snapshot["candidates"][0]
    assert candidate["gross_margin_pass_v1"] is True
    assert candidate["gross_margin_source"] == "revenue_minus_cost_of_revenue"
    assert candidate["cost_of_revenue_filed"] == "2026-04-25"
    assert snapshot["trade_enabled"] is False


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
    assert candidate["filing_timeliness_pass_v1"] is True
    assert candidate["filing_timeliness_notional_scalar"] == 1.05
    assert candidate["closed_ledger_notional_scalar"] == 1.21275
    assert candidate["intended_notional"] == 12_127.5
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
    assert candidate["closed_ledger_notional_scalar"] == 1.1025
    assert candidate["intended_notional"] == 11_025.0
    assert snapshot["filing_recency"]["supported_candidate_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False


def test_filing_timeliness_support_scales_paper_notional_without_orders():
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
    assert candidate["filing_timeliness_rule_version"] == FILING_TIMELINESS_RULE_VERSION
    assert candidate["filing_timeliness_lag_days"] == 25
    assert candidate["filing_timeliness_max_days"] == 45
    assert candidate["filing_timeliness_bucket"] == "timely"
    assert candidate["filing_timeliness_pass_v1"] is True
    assert candidate["filing_timeliness_notional_scalar"] == 1.05
    assert candidate["closed_ledger_notional_scalar"] == 1.1025
    assert candidate["intended_notional"] == 11_025.0
    assert snapshot["filing_timeliness"]["supported_candidate_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False


def test_late_filing_timeliness_does_not_scale_paper_notional_without_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][125]["date"]
    facts = []
    for row in _facts():
        updated = dict(row)
        if updated["canonical"] == "operating_income" and updated["fy"] == 2026:
            updated["end"] = "2026-01-01"
        facts.append(updated)

    snapshot = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=facts,
        candidate_universe=["AMD", "AAPL"],
        state=empty_fundamental_growth_rs_paper_state(),
        persist=False,
    )

    candidate = snapshot["candidates"][0]
    assert candidate["filing_timeliness_lag_days"] == 114
    assert candidate["filing_timeliness_max_days"] == 45
    assert candidate["filing_timeliness_bucket"] == "late"
    assert candidate["filing_timeliness_pass_v1"] is False
    assert candidate["filing_timeliness_notional_scalar"] == 1.0
    assert candidate["closed_ledger_notional_scalar"] == 1.05
    assert candidate["intended_notional"] == 10_500.0
    assert snapshot["filing_timeliness"]["supported_candidate_count"] == 0
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False


def test_low_liability_support_scales_paper_notional_without_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][125]["date"]

    snapshot = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=_low_liability_facts(),
        candidate_universe=["AMD", "AAPL"],
        state=empty_fundamental_growth_rs_paper_state(),
        persist=False,
    )

    candidate = snapshot["candidates"][0]
    assert candidate["low_liability_rule_version"] == LOW_LIABILITY_RULE_VERSION
    assert candidate["liabilities_assets_ratio"] == 0.25
    assert candidate["liabilities_assets_bucket"] == "low_lte_0p35"
    assert candidate["low_liability_assets_max"] == 0.35
    assert candidate["low_liability_pass_v1"] is True
    assert candidate["low_liability_notional_scalar"] == 1.05
    assert candidate["filing_recency_pass_v1"] is True
    assert candidate["filing_timeliness_pass_v1"] is True
    assert candidate["closed_ledger_notional_scalar"] == 1.157625
    assert candidate["intended_notional"] == 11_576.25
    assert snapshot["low_liability"]["supported_candidate_count"] == 1
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
    assert candidate["filing_timeliness_pass_v1"] is True
    assert candidate["closed_ledger_notional_scalar"] == 0.013781
    assert candidate["intended_notional"] == 137.81


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
    # Freshly filled position starts at 0 observed days so the realized hold spans
    # the full hold_days horizon (advance runs before fill, so the entry day is
    # never advanced). Must match the codebase-wide convention used by every other
    # sleeve; starting at 1 would exit one trading day early (9-day hold for a
    # hold_days=10 sleeve) and misalign forward_outcome_horizon_days.
    assert second["open_positions"][0]["observed_trading_days"] == 0

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


def test_non_trading_asof_does_not_fill_pending_with_stale_open():
    ohlcv = _trading_ohlcv()
    friday_idx, friday = _late_friday(ohlcv["SPY"])
    saturday = (date.fromisoformat(friday) + timedelta(days=1)).isoformat()

    first = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=friday,
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=_facts(),
        candidate_universe=["AMD", "AAPL"],
        state=empty_fundamental_growth_rs_paper_state(),
        persist=False,
    )
    state = empty_fundamental_growth_rs_paper_state()
    state["pending_entries"] = first["pending_entries"]

    weekend = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=saturday,
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=_facts(),
        candidate_universe=["AMD", "AAPL"],
        state=state,
        open_prices={"AMD": ohlcv["AMD"][friday_idx]["open"]},
        current_prices={"AMD": ohlcv["AMD"][friday_idx]["close"]},
        persist=False,
    )

    assert weekend["price_data"]["exact_close_ticker_count"] == 0
    assert weekend["filled_count"] == 0
    assert weekend["pending_count"] == 1
    assert weekend["open_position_count"] == 0


def test_non_trading_asof_does_not_advance_open_position_hold_days():
    ohlcv = _trading_ohlcv()
    friday_idx, friday = _late_friday(ohlcv["SPY"])
    saturday = (date.fromisoformat(friday) + timedelta(days=1)).isoformat()
    state = empty_fundamental_growth_rs_paper_state()
    state["open_positions"] = [
        {
            "ticker": "AMD",
            "entry_date": ohlcv["AMD"][friday_idx - 9]["date"],
            "entry_price": ohlcv["AMD"][friday_idx - 9]["open"],
            "notional": 10_000.0,
            "observed_trading_days": 9,
            "status": "open",
            "trade_enabled": False,
        }
    ]

    weekend = build_fundamental_growth_rs_paper_sleeve_snapshot(
        as_of=saturday,
        ohlcv_by_ticker=ohlcv,
        companyfacts_rows=_facts(),
        candidate_universe=["AMD", "AAPL"],
        state=state,
        current_prices={"AMD": ohlcv["AMD"][friday_idx]["close"]},
        persist=False,
    )

    assert weekend["price_data"]["exact_close_ticker_count"] == 0
    assert weekend["closed_count_today"] == 0
    assert weekend["open_position_count"] == 1
    assert weekend["open_positions"][0]["observed_trading_days"] == 9


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
        "gross_margin_quality": {"candidate_count": 1},
        "filing_timeliness": {"supported_candidate_count": 1},
        "low_liability": {"supported_candidate_count": 1},
    }

    report = build_default_off_alpha_attribution_report(
        as_of="2026-05-28",
        fundamental_growth_rs_paper_sleeve=sleeve,
    )

    surfaces = {row["name"]: row for row in report["surfaces"]}
    assert "fundamental_growth_rs" in surfaces
    assert surfaces["fundamental_growth_rs"]["label"] == "FUNDAMENTAL_GROWTH_RS_PAPER"
    assert surfaces["fundamental_growth_rs"]["trade_enabled"] is False
    assert surfaces["fundamental_growth_rs"]["extra_metrics"]["gross_margin_quality_candidates"] == 1
    assert surfaces["fundamental_growth_rs"]["extra_metrics"]["filing_timeliness_supported"] == 1
    assert surfaces["fundamental_growth_rs"]["extra_metrics"]["low_liability_supported"] == 1
    assert "min_closed_trades" in surfaces["fundamental_growth_rs"]["blockers"]
