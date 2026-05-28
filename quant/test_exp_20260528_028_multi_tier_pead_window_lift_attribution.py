"""Unit tests for exp-20260528-028 multi-tier PEAD window attribution.

Tests cover per-tier bucket construction, gate accept / reject /
observed-only logic on synthetic stats, and that all three tier flags
are independently honored.

No JavaScript was used.
"""

from __future__ import annotations

from quant.experiments.exp_20260528_028_multi_tier_pead_window_lift_attribution_no_residual_filter import (  # noqa: E501
    LIFT_FLOOR,
    PUBLISHED_GATE_THRESHOLDS,
    TIER_FLAGS,
    attribute_tier,
    evaluate_gates,
    horizon_stats,
    tier_comparisons,
)


def _row(
    *,
    primary=False,
    wide=False,
    scout=False,
    last_earnings="2026-05-05",
    pead_window=True,
    ticker="AAPL",
    forward_5d=None,
    forward_10d=None,
):
    return {
        "ticker": ticker,
        "primary_expectation_positive": primary,
        "wide_watchlist_positive": wide,
        "scout_prev_positive": scout,
        "last_earnings_date": last_earnings,
        "pead_window": pead_window,
        "forward_outcomes": {
            "5d": forward_5d or {"closed": False},
            "10d": forward_10d or {"closed": False},
            "20d": {"closed": False},
        },
    }


def test_tier_flags_are_independent():
    assert tuple(TIER_FLAGS) == (
        "primary_expectation_positive",
        "wide_watchlist_positive",
        "scout_prev_positive",
    )


def test_attribute_tier_partitions_into_in_out_baseline():
    rows = [
        _row(
            primary=True,
            pead_window=True,
            ticker="A",
            forward_5d={"closed": True, "return": 0.05, "pnl_proxy": 500.0},
        ),
        _row(
            primary=True,
            pead_window=False,
            ticker="B",
            forward_5d={"closed": True, "return": 0.02, "pnl_proxy": 200.0},
        ),
        # baseline row (not in primary).
        _row(
            primary=False,
            ticker="C",
            forward_5d={"closed": True, "return": 0.01, "pnl_proxy": 100.0},
        ),
    ]
    stats = attribute_tier(rows, "primary_expectation_positive")
    assert stats["primary_expectation_positive_pead_in"]["row_count"] == 1
    assert stats["primary_expectation_positive_pead_out"]["row_count"] == 1
    assert stats["primary_expectation_positive_baseline_not_in_tier"]["row_count"] == 1


def test_attribute_tier_skips_tier_rows_without_last_earnings_date():
    rows = [
        _row(primary=True, last_earnings=None, pead_window=False, ticker="A"),
        _row(primary=True, last_earnings="2026-05-05", pead_window=True, ticker="B"),
    ]
    stats = attribute_tier(rows, "primary_expectation_positive")
    # First row has missing last_earnings_date so should not enter
    # pead_in *or* pead_out (we cannot decide for it).
    assert stats["primary_expectation_positive_pead_in"]["row_count"] == 1
    assert stats["primary_expectation_positive_pead_out"]["row_count"] == 0


def test_horizon_stats_handles_empty_input():
    out = horizon_stats([], "5d")
    assert out["row_count"] == 0
    assert out["closed_count"] == 0
    assert out["avg_return"] is None
    assert out["win_rate"] is None


def _make_stats(*, tier, in_avg, out_avg, baseline_avg, in_closed=10, out_closed=10):
    return {
        f"{tier}_pead_in": {
            "row_count": in_closed,
            "5d": {
                "row_count": in_closed,
                "closed_count": in_closed,
                "avg_return": in_avg,
                "win_rate": 0.5,
                "tail_loss": -0.02,
                "total_pnl_proxy": 0.0,
                "positive_pnl_proxy": 200.0,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
            "10d": {
                "row_count": in_closed,
                "closed_count": in_closed,
                "avg_return": in_avg,
                "win_rate": 0.5,
                "tail_loss": -0.02,
                "total_pnl_proxy": 0.0,
                "positive_pnl_proxy": 200.0,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
        },
        f"{tier}_pead_out": {
            "row_count": out_closed,
            "5d": {
                "row_count": out_closed,
                "closed_count": out_closed,
                "avg_return": out_avg,
                "win_rate": 0.5,
                "tail_loss": -0.02,
                "total_pnl_proxy": 0.0,
                "positive_pnl_proxy": 200.0,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
            "10d": {
                "row_count": out_closed,
                "closed_count": out_closed,
                "avg_return": out_avg,
                "win_rate": 0.5,
                "tail_loss": -0.02,
                "total_pnl_proxy": 0.0,
                "positive_pnl_proxy": 200.0,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
        },
        f"{tier}_baseline_not_in_tier": {
            "row_count": 50,
            "5d": {
                "row_count": 50,
                "closed_count": 50,
                "avg_return": baseline_avg,
                "win_rate": 0.5,
                "tail_loss": -0.02,
                "total_pnl_proxy": 0.0,
                "positive_pnl_proxy": 500.0,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
            "10d": {
                "row_count": 50,
                "closed_count": 50,
                "avg_return": baseline_avg,
                "win_rate": 0.5,
                "tail_loss": -0.02,
                "total_pnl_proxy": 0.0,
                "positive_pnl_proxy": 500.0,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
        },
    }


def test_gate4_rejects_when_all_three_tiers_show_non_positive_lift():
    stats = {}
    for tier in TIER_FLAGS:
        stats.update(
            _make_stats(tier=tier, in_avg=0.0, out_avg=0.01, baseline_avg=0.005)
        )
    comps = []
    for tier in TIER_FLAGS:
        comps.extend(tier_comparisons(stats, tier, PUBLISHED_GATE_THRESHOLDS))
    gates = evaluate_gates(comps, stats, PUBLISHED_GATE_THRESHOLDS)
    assert gates["gate4"]["status"] == "rejected_no_pead_window_lift_across_tiers"
    assert gates["gate4"]["passed"] is False


def test_gate4_accepts_when_at_least_one_tier_lifts_above_floor():
    stats = {}
    for i, tier in enumerate(TIER_FLAGS):
        # primary tier wins; others are flat.
        in_avg = 0.03 if i == 0 else 0.0
        stats.update(
            _make_stats(tier=tier, in_avg=in_avg, out_avg=0.0, baseline_avg=0.005)
        )
    comps = []
    for tier in TIER_FLAGS:
        comps.extend(tier_comparisons(stats, tier, PUBLISHED_GATE_THRESHOLDS))
    gates = evaluate_gates(comps, stats, PUBLISHED_GATE_THRESHOLDS)
    assert gates["gate4"]["status"] == "accepted_pead_window_lift_in_some_tier"
    assert gates["gate4"]["passed"] is True


def test_gate4_observed_only_when_mixed_signs_below_floor():
    stats = {}
    for i, tier in enumerate(TIER_FLAGS):
        in_avg = 0.001 if i == 0 else (-0.001 if i == 1 else 0.005)
        stats.update(
            _make_stats(tier=tier, in_avg=in_avg, out_avg=0.0, baseline_avg=0.005)
        )
    comps = []
    for tier in TIER_FLAGS:
        comps.extend(tier_comparisons(stats, tier, PUBLISHED_GATE_THRESHOLDS))
    gates = evaluate_gates(comps, stats, PUBLISHED_GATE_THRESHOLDS)
    # One positive lift +0.005 below LIFT_FLOOR=0.01, one negative, one
    # positive at +0.005. Not all non-positive (so not rejected) and
    # none meet the floor (so not accepted) -> observed_only.
    assert gates["gate4"]["status"] == "observed_only_no_consistent_pead_window_lift"
    assert gates["gate4"]["passed"] is False


def test_gate4_per_tier_diagnostic_contains_each_tier():
    stats = {}
    for tier in TIER_FLAGS:
        stats.update(
            _make_stats(tier=tier, in_avg=0.0, out_avg=0.005, baseline_avg=0.001)
        )
    comps = []
    for tier in TIER_FLAGS:
        comps.extend(tier_comparisons(stats, tier, PUBLISHED_GATE_THRESHOLDS))
    gates = evaluate_gates(comps, stats, PUBLISHED_GATE_THRESHOLDS)
    per_tier = gates["gate4"]["per_tier_5d_diagnostic"]
    for tier in TIER_FLAGS:
        assert tier in per_tier
        assert "lift" in per_tier[tier]
        assert "accepted" in per_tier[tier]
