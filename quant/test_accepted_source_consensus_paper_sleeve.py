from __future__ import annotations

from datetime import date, timedelta

from quant.accepted_source_consensus_paper_sleeve import (
    RULE_VERSION,
    SLEEVE_NAME,
    build_accepted_source_consensus_paper_sleeve_snapshot,
    empty_accepted_source_consensus_paper_state,
)
from quant.default_off_alpha_attribution import build_default_off_alpha_attribution_report


def _rows(
    *,
    base: float = 50.0,
    step: float = 0.10,
    days: int = 72,
    volume: float = 1_000_000.0,
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
                "volume": volume,
            }
        )
    return rows


def _features() -> dict[str, dict]:
    features = {
        "WIN": {
            "trend_score": 1.0,
            "breakout_20d": True,
            "above_200ma": True,
            "momentum_20d_pct": 0.40,
            "momentum_60d_pct": 0.80,
            "avg_historical_surprise_pct": 10.0,
        }
    }
    for idx in range(12):
        features[f"L{idx:02d}"] = {
            "trend_score": 0.20,
            "breakout_20d": False,
            "above_200ma": True,
            "momentum_20d_pct": -0.05,
            "momentum_60d_pct": 0.02,
        }
    return features


def _ohlcv() -> dict[str, list[dict]]:
    ohlcv = {
        "SPY": _rows(base=100.0, step=0.08),
        "IWM": _rows(base=100.0, step=0.22),
        "WIN": _rows(base=80.0, step=0.10, volume=1_200_000.0),
    }
    for idx in range(12):
        ohlcv[f"L{idx:02d}"] = _rows(base=45.0 + idx, step=0.03)
    return ohlcv


def test_consensus_sleeve_requires_external_accepted_source_overlap():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][60]["date"]

    snapshot = build_accepted_source_consensus_paper_sleeve_snapshot(
        as_of=as_of,
        features_by_ticker=_features(),
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(_features()),
        state=empty_accepted_source_consensus_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["raw_alpha_score_candidate_count"] == 1
    assert snapshot["source_consensus"]["supported_candidate_count"] == 0
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False
    assert "missing_accepted_source_consensus" in snapshot["rejected_candidates"][0]["reasons"]


def test_consensus_sleeve_admits_overlap_without_scaling_notional_or_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][60]["date"]

    snapshot = build_accepted_source_consensus_paper_sleeve_snapshot(
        as_of=as_of,
        features_by_ticker=_features(),
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(_features()),
        source_consensus_snapshots=[
            {
                "sleeve": "VOLUME_BREADTH_BREAKOUT_PAPER",
                "candidates": [{"ticker": "WIN", "signal_date": as_of}],
            }
        ],
        state=empty_accepted_source_consensus_paper_state(),
        persist=False,
    )

    assert snapshot["sleeve"] == SLEEVE_NAME
    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "WIN"
    assert candidate["rule_version"] == RULE_VERSION
    assert candidate["accepted_source_consensus_candidate_pool"] is True
    assert candidate["accepted_source_consensus_sources"] == ["VOLUME_BREADTH_BREAKOUT_PAPER"]
    assert candidate["source_consensus_support_applied"] is False
    assert candidate["intended_notional"] == 4_000.0
    assert snapshot["new_pending_entries"][0]["notional"] == 4_000.0
    assert snapshot["trade_enabled"] is False
    assert candidate["alters_orders"] is False


def test_default_off_attribution_includes_accepted_source_consensus_surface():
    report = build_default_off_alpha_attribution_report(
        as_of="2026-03-02",
        accepted_source_consensus_paper_sleeve={
            "sleeve": "ACCEPTED_SOURCE_CONSENSUS_PAPER",
            "source_rule_version": "full_universe_alpha_score_top1_20d_v1",
            "market_regime_rule_version": "alpha_score_market_regime_risk_appetite_v1",
            "candidate_count": 1,
            "pending_count": 1,
            "raw_alpha_score_candidate_count": 3,
            "source_consensus": {
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
    assert "accepted_source_consensus" in surfaces
    assert surfaces["accepted_source_consensus"]["status"] == "blocked"
    extra = surfaces["accepted_source_consensus"]["extra_metrics"]
    assert extra["paper_notional_usd"] == 4_000.0
    assert extra["raw_alpha_score_candidate_count"] == 3
    assert extra["source_consensus_supported"] == 1
