from __future__ import annotations

from datetime import date, timedelta

from quant.alpha_score_market_regime_paper_sleeve import (
    MARKET_REGIME_RULE_VERSION,
    RULE_VERSION,
    SAFE_NOTIONAL_RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_alpha_score_market_regime_paper_sleeve_snapshot,
    empty_alpha_score_market_regime_paper_state,
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


def _ohlcv(*, iwm_lags: bool = False) -> dict[str, list[dict]]:
    ohlcv = {
        "SPY": _rows(base=100.0, step=0.08),
        "IWM": _rows(base=100.0, step=0.02 if iwm_lags else 0.22),
        "WIN": _rows(base=80.0, step=0.10, volume=1_200_000.0),
    }
    for idx in range(12):
        ohlcv[f"L{idx:02d}"] = _rows(base=45.0 + idx, step=0.03)
    return ohlcv


def test_alpha_score_market_regime_snapshot_admits_top_candidate_without_orders():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][60]["date"]

    snapshot = build_alpha_score_market_regime_paper_sleeve_snapshot(
        as_of=as_of,
        features_by_ticker=_features(),
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(_features()),
        state=empty_alpha_score_market_regime_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["pending_count"] == 1
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False
    assert snapshot["market_regime_context"]["rule_version"] == MARKET_REGIME_RULE_VERSION
    assert snapshot["market_regime_context"]["passed"] is True
    assert snapshot["ranking_surface"]["top_decile_count"] == 1
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "WIN"
    assert candidate["rule_version"] == RULE_VERSION
    assert candidate["source_rule_version"] == SOURCE_RULE_VERSION
    assert candidate["safe_notional_rule_version"] == SAFE_NOTIONAL_RULE_VERSION
    assert candidate["alpha_score_bucket"] == "top_decile"
    assert candidate["intended_notional"] == 4_000.0
    assert candidate["safe_notional_scalar"] == 0.4
    assert candidate["source_consensus_support_applied"] is False
    assert candidate["source_consensus_paper_notional_usd"] == 4_000.0
    assert candidate["trade_enabled"] is False
    assert candidate["alters_orders"] is False


def test_source_consensus_support_scales_default_off_paper_notional_only():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][60]["date"]

    snapshot = build_alpha_score_market_regime_paper_sleeve_snapshot(
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
        state=empty_alpha_score_market_regime_paper_state(),
        persist=False,
    )

    candidate = snapshot["candidates"][0]
    support = snapshot["source_consensus_support"]
    assert candidate["ticker"] == "WIN"
    assert candidate["source_consensus_support_applied"] is True
    assert candidate["source_consensus_sources"] == ["VOLUME_BREADTH_BREAKOUT_PAPER"]
    assert candidate["source_consensus_notional_scalar"] == 1.25
    assert candidate["safe_paper_notional_usd"] == 4_000.0
    assert candidate["intended_notional"] == 5_000.0
    assert snapshot["new_pending_entries"][0]["notional"] == 5_000.0
    assert support["supported_candidate_count"] == 1
    assert support["source_counts"] == {"VOLUME_BREADTH_BREAKOUT_PAPER": 1}
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["production_orders_changed"] is False


def test_market_regime_gate_blocks_when_iwm_lags_spy():
    ohlcv = _ohlcv(iwm_lags=True)
    as_of = ohlcv["SPY"][60]["date"]

    snapshot = build_alpha_score_market_regime_paper_sleeve_snapshot(
        as_of=as_of,
        features_by_ticker=_features(),
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(_features()),
        state=empty_alpha_score_market_regime_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["rejected_candidate_count"] == 1
    assert snapshot["market_regime_context"]["reason"] == "iwm_lagging_spy_20d"
    assert "market_regime_gate_failed" in snapshot["rejected_candidates"][0]["reasons"]
    assert snapshot["production_impact"]["trade_enabled"] is False


def test_stale_missing_asof_price_does_not_fill_pending_entry():
    ohlcv = _ohlcv()
    as_of = ohlcv["SPY"][60]["date"]
    stale_ohlcv = dict(ohlcv)
    stale_ohlcv["WIN"] = [row for row in ohlcv["WIN"] if row["date"] != as_of]
    state = empty_alpha_score_market_regime_paper_state()
    state["pending_entries"].append(
        {
            "decision_id": "test",
            "sleeve": "ALPHA_SCORE_MARKET_REGIME_PAPER",
            "ticker": "WIN",
            "created_asof": (date.fromisoformat(as_of) - timedelta(days=1)).isoformat(),
            "status": "pending_next_open",
            "notional": 4_000.0,
            "candidate": {"ticker": "WIN", "date": as_of},
            "trade_enabled": False,
        }
    )

    snapshot = build_alpha_score_market_regime_paper_sleeve_snapshot(
        as_of=as_of,
        features_by_ticker=_features(),
        ohlcv_by_ticker=stale_ohlcv,
        candidate_universe=list(_features()),
        open_prices={"WIN": 999.0},
        state=state,
        persist=False,
    )

    assert snapshot["filled_count"] == 0
    assert snapshot["pending_count"] == 0
    assert snapshot["skipped_entries_today"][0]["status"] == "skipped_missing_next_open"
    assert snapshot["open_position_count"] == 0


def _two_strong_features() -> dict[str, dict]:
    features = {
        "WIN": {
            "trend_score": 1.0,
            "breakout_20d": True,
            "above_200ma": True,
            "momentum_20d_pct": 0.40,
            "momentum_60d_pct": 0.80,
            "avg_historical_surprise_pct": 10.0,
        },
        "WIN2": {
            "trend_score": 0.9,
            "breakout_20d": True,
            "above_200ma": True,
            "momentum_20d_pct": 0.35,
            "momentum_60d_pct": 0.70,
            "avg_historical_surprise_pct": 8.0,
        },
    }
    # Enough weak names that the top-decile bucket admits two strong candidates
    # (WIN + WIN2), so the daily-slot idempotency guard is actually exercised.
    for idx in range(18):
        features[f"L{idx:02d}"] = {
            "trend_score": 0.20,
            "breakout_20d": False,
            "above_200ma": True,
            "momentum_20d_pct": -0.05,
            "momentum_60d_pct": 0.02,
        }
    return features


def _two_strong_ohlcv() -> dict[str, list[dict]]:
    ohlcv = {
        "SPY": _rows(base=100.0, step=0.08),
        "IWM": _rows(base=100.0, step=0.22),
        "WIN": _rows(base=80.0, step=0.10, volume=1_200_000.0),
        "WIN2": _rows(base=78.0, step=0.095, volume=1_150_000.0),
    }
    for idx in range(18):
        ohlcv[f"L{idx:02d}"] = _rows(base=45.0 + idx, step=0.03)
    return ohlcv


def test_same_signal_day_rerun_is_idempotent_and_does_not_double_admit():
    """A second same-day run must not grant a fresh daily slot to the next-ranked
    candidate once the top pick is already pending (the CAT/GEV bug: two pending
    entries for one signal day when daily_entry_slots == 1)."""
    ohlcv = _two_strong_ohlcv()
    features = _two_strong_features()
    as_of = ohlcv["SPY"][60]["date"]

    first = build_alpha_score_market_regime_paper_sleeve_snapshot(
        as_of=as_of,
        features_by_ticker=features,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(features),
        state=empty_alpha_score_market_regime_paper_state(),
        persist=False,
    )
    # Run 1 admits exactly the top pick (WIN); WIN2 is held back by the daily slot.
    assert first["new_pending_count"] == 1
    assert first["pending_count"] == 1
    assert first["pending_entries"][0]["ticker"] == "WIN"

    state_after = empty_alpha_score_market_regime_paper_state()
    state_after["pending_entries"] = first["pending_entries"]
    state_after["open_positions"] = first["open_positions"]
    state_after["closed_positions"] = first["closed_positions"]

    second = build_alpha_score_market_regime_paper_sleeve_snapshot(
        as_of=as_of,
        features_by_ticker=features,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=list(features),
        state=state_after,
        persist=False,
    )
    # WIN2 is still a valid (non-pending) candidate on the re-run, so the only
    # thing that can keep it out is the daily-slot idempotency guard - not the
    # already-pending exclusion. Assert it stays out anyway.
    assert [c["ticker"] for c in second["candidates"]] == ["WIN2"]
    assert second["new_pending_count"] == 0
    assert second["pending_count"] == 1
    pending_tickers = [row["ticker"] for row in second["pending_entries"]]
    assert pending_tickers == ["WIN"]
    win2_reject = next(
        c for c in second["rejected_candidates"] if c["ticker"] == "WIN2"
    )
    assert "daily_top1_or_capacity_limit" in win2_reject["reasons"]


def test_default_off_alpha_attribution_includes_alpha_score_market_regime_surface():
    report = build_default_off_alpha_attribution_report(
        as_of="2026-03-02",
        alpha_score_market_regime_paper_sleeve={
            "sleeve": "ALPHA_SCORE_MARKET_REGIME_PAPER",
            "source_rule_version": SOURCE_RULE_VERSION,
            "market_regime_rule_version": MARKET_REGIME_RULE_VERSION,
            "candidate_count": 1,
            "pending_count": 1,
            "ranking_surface": {"ranked_count": 13, "top_decile_count": 1},
            "source_consensus_support": {
                "supported_candidate_count": 1,
                "source_counts": {"FINRA_IWM_CONFIRMED_PAPER": 1},
            },
            "candidates": [{"safe_paper_notional_usd": 4_000.0}],
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["min_closed_trades"],
                "metrics": {"closed_trades": 0, "realized_pnl": 0.0},
            },
        },
    )

    surfaces = {row["name"]: row for row in report["surfaces"]}
    assert "alpha_score_market_regime" in surfaces
    assert surfaces["alpha_score_market_regime"]["status"] == "blocked"
    extra = surfaces["alpha_score_market_regime"]["extra_metrics"]
    assert extra["source_rule_version"] == SOURCE_RULE_VERSION
    assert extra["safe_notional_usd"] == 4_000.0
    assert extra["top_decile_count"] == 1
    assert extra["source_consensus_supported"] == 1
