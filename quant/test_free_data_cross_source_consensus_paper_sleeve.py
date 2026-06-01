from __future__ import annotations

from datetime import date, timedelta

from quant.default_off_alpha_attribution import build_default_off_alpha_attribution_report
from quant.free_data_cross_source_consensus_paper_sleeve import (
    RULE_VERSION,
    SLEEVE_NAME,
    build_free_data_cross_source_consensus_paper_sleeve_snapshot,
    empty_free_data_cross_source_consensus_paper_state,
)


def _rows(
    *,
    base: float = 50.0,
    step: float = 0.10,
    days: int = 30,
) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(days):
        close = base + step * idx
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": round(close * 0.995, 4),
                "high": round(close * 1.01, 4),
                "low": round(close * 0.99, 4),
                "close": round(close, 4),
                "volume": 1_000_000.0,
            }
        )
    return rows


def test_cross_source_consensus_requires_two_accepted_sources():
    as_of = "2026-01-12"
    snapshot = build_free_data_cross_source_consensus_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={"WIN": _rows(base=80.0), "SPY": _rows(base=100.0)},
        source_snapshots=[
            {
                "sleeve": "VOLUME_BREADTH_BREAKOUT_PAPER",
                "asof_date": as_of,
                "candidates": [{"ticker": "WIN", "signal_date": as_of}],
            }
        ],
        state=empty_free_data_cross_source_consensus_paper_state(),
        core_active_position_count=0,
        max_core_positions=5,
        persist=False,
    )

    assert snapshot["sleeve"] == SLEEVE_NAME
    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["source_consensus_key_count"] == 1
    assert snapshot["rejected_candidates"][0]["reasons"] == ["insufficient_source_count"]
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False


def test_cross_source_consensus_admits_same_ticker_same_date_without_orders():
    as_of = "2026-01-12"
    snapshot = build_free_data_cross_source_consensus_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={"WIN": _rows(base=80.0), "SPY": _rows(base=100.0)},
        source_snapshots=[
            {
                "sleeve": "VOLUME_BREADTH_BREAKOUT_PAPER",
                "asof_date": as_of,
                "candidates": [{"ticker": "WIN", "signal_date": as_of}],
            },
            {
                "sleeve": "FINRA_IWM_CONFIRMED_PAPER",
                "asof_date": as_of,
                "candidates": [{"ticker": "WIN", "signal_date": as_of}],
            },
        ],
        state=empty_free_data_cross_source_consensus_paper_state(),
        core_active_position_count=4,
        max_core_positions=5,
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "WIN"
    assert candidate["rule_version"] == RULE_VERSION
    assert candidate["cross_source_consensus_candidate_pool"] is True
    assert candidate["core_capacity_rule_version"] == "accepted_free_data_consensus_core_capacity_available_gate_v1"
    assert candidate["active_core_positions_after_signal_close"] == 4
    assert candidate["available_core_slots_after_signal_close"] == 1
    assert candidate["source_count"] == 2
    assert candidate["source_names"] == [
        "FINRA_IWM_CONFIRMED_PAPER",
        "VOLUME_BREADTH_BREAKOUT_PAPER",
    ]
    assert candidate["intended_notional"] == 4_000.0
    assert candidate["alters_orders"] is False
    assert snapshot["new_pending_entries"][0]["notional"] == 4_000.0
    assert snapshot["core_capacity_gate"]["passed"] is True
    assert snapshot["trade_enabled"] is False


def test_cross_source_consensus_rejects_when_core_capacity_full():
    as_of = "2026-01-12"
    snapshot = build_free_data_cross_source_consensus_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={"WIN": _rows(base=80.0), "SPY": _rows(base=100.0)},
        source_snapshots=[
            {
                "sleeve": "VOLUME_BREADTH_BREAKOUT_PAPER",
                "asof_date": as_of,
                "candidates": [{"ticker": "WIN", "signal_date": as_of}],
            },
            {
                "sleeve": "FINRA_IWM_CONFIRMED_PAPER",
                "asof_date": as_of,
                "candidates": [{"ticker": "WIN", "signal_date": as_of}],
            },
        ],
        state=empty_free_data_cross_source_consensus_paper_state(),
        core_active_position_count=5,
        max_core_positions=5,
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["core_capacity_gate"]["passed"] is False
    assert snapshot["core_capacity_gate"]["reasons"] == ["core_capacity_full"]
    assert snapshot["rejected_candidates"][0]["reasons"] == ["core_capacity_full"]
    assert snapshot["trade_enabled"] is False


def test_cross_source_consensus_rejects_missing_core_capacity_context():
    as_of = "2026-01-12"
    snapshot = build_free_data_cross_source_consensus_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={"WIN": _rows(base=80.0), "SPY": _rows(base=100.0)},
        source_snapshots=[
            {
                "sleeve": "VOLUME_BREADTH_BREAKOUT_PAPER",
                "asof_date": as_of,
                "candidates": [{"ticker": "WIN", "signal_date": as_of}],
            },
            {
                "sleeve": "FINRA_IWM_CONFIRMED_PAPER",
                "asof_date": as_of,
                "candidates": [{"ticker": "WIN", "signal_date": as_of}],
            },
        ],
        state=empty_free_data_cross_source_consensus_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["core_capacity_gate"]["passed"] is False
    assert snapshot["core_capacity_gate"]["reasons"] == ["missing_core_capacity_context"]
    assert snapshot["rejected_candidates"][0]["reasons"] == ["missing_core_capacity_context"]
    assert snapshot["trade_enabled"] is False


def test_default_off_attribution_includes_cross_source_consensus_surface():
    report = build_default_off_alpha_attribution_report(
        as_of="2026-01-12",
        free_data_cross_source_consensus_paper_sleeve={
            "sleeve": SLEEVE_NAME,
            "consensus_rule_version": "accepted_free_data_cross_source_consensus_candidate_pool_v1",
            "candidate_count": 1,
            "pending_count": 1,
            "source_consensus": {
                "min_source_count": 2,
                "supported_candidate_count": 1,
                "paper_notional_usd": 4_000.0,
                "source_counts": {"FINRA_IWM_CONFIRMED_PAPER": 1},
            },
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["min_closed_trades"],
                "metrics": {"closed_trades": 0, "realized_pnl": 0.0},
            },
        },
    )

    surfaces = {row["name"]: row for row in report["surfaces"]}
    assert "free_data_cross_source_consensus" in surfaces
    surface = surfaces["free_data_cross_source_consensus"]
    assert surface["status"] == "blocked"
    assert surface["extra_metrics"]["paper_notional_usd"] == 4_000.0
    assert surface["extra_metrics"]["min_source_count"] == 2
    assert surface["extra_metrics"]["source_consensus_supported"] == 1
