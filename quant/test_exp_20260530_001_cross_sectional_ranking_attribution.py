"""Unit tests for exp-20260530-001 cross-sectional ranking attribution judge.

Covers aggregation folding and the gate decision branches: degenerate
rank (observed_only), clean monotonic (accepted), inverted (rejected),
and insufficient PIT coverage.

No JavaScript was used.
"""

from __future__ import annotations

from quant.experiments.exp_20260530_001_cross_sectional_ranking_predictive_power_attribution import (  # noqa: E501
    MIN_BUCKET_TRADES,
    PIT_COVERAGE_FLOOR,
    aggregate,
    judge,
)


def _report(*, trades, pit_cov, rank_buckets, component_attribution):
    return {
        "coverage": {
            "trades_total": trades,
            "point_in_time_safe_trades": round(trades * pit_cov),
            "point_in_time_safe_coverage": pit_cov,
            "trades_with_alpha_score": trades,
            "policy_research_ready": pit_cov >= PIT_COVERAGE_FLOOR,
        },
        "ranking_bucket_attribution": rank_buckets,
        "component_attribution": component_attribution,
    }


def _bucket(name, trades, avg_r=1.0, win=0.5, total_pnl=1000.0):
    return {
        "bucket": name,
        "trades": trades,
        "avg_r": avg_r,
        "win_rate": win,
        "total_pnl": total_pnl,
    }


def test_aggregate_folds_across_windows():
    reports = {
        "w1": _report(
            trades=10,
            pit_cov=1.0,
            rank_buckets=[_bucket("top_decile", 10, total_pnl=1000.0)],
            component_attribution={
                "trend": {"buckets": [_bucket("high", 10)]},
            },
        ),
        "w2": _report(
            trades=6,
            pit_cov=1.0,
            rank_buckets=[_bucket("top_decile", 6, total_pnl=600.0)],
            component_attribution={
                "trend": {"buckets": [_bucket("high", 6)]},
            },
        ),
    }
    agg = aggregate(reports)
    assert agg["total_trades"] == 16
    assert agg["overall_pit_coverage"] == 1.0
    assert agg["rank_bucket_summary"]["top_decile"]["trades"] == 16
    assert agg["rank_bucket_summary"]["top_decile"]["total_pnl"] == 1600.0


def test_judge_degenerate_rank_observed_only():
    # All trades in top_decile/top_quartile, constant trend -> observed_only.
    reports = {
        "w1": _report(
            trades=20,
            pit_cov=1.0,
            rank_buckets=[_bucket("top_decile", 19), _bucket("top_quartile", 1)],
            component_attribution={
                "trend": {"buckets": [_bucket("high", 20)]},
                "expectation_revision": {"buckets": [_bucket("mid", 20)]},
            },
        ),
    }
    gates = judge(aggregate(reports))
    assert gates["gate4"]["status"] == "observed_only_rank_degenerate_requires_full_universe"
    assert gates["all_passed"] is False
    assert gates["gate4"]["rank_degenerate_no_bottom_group"] is True
    assert set(gates["gate4"]["constant_components_zero_info"]) == {
        "trend",
        "expectation_revision",
    }


def test_judge_accepts_clean_monotonic_dispersed_component():
    # Rank spans a bottom group AND a dispersed component is cleanly monotonic.
    reports = {
        "w1": _report(
            trades=40,
            pit_cov=1.0,
            rank_buckets=[
                _bucket("top_decile", 10),
                _bucket("upper_mid", 15),  # bottom group present
                _bucket("lower_mid", 15),
            ],
            component_attribution={
                "relative_strength": {
                    "buckets": [
                        _bucket("high", 20, avg_r=1.8),
                        _bucket("mid", 20, avg_r=1.0),  # margin 0.8 >= 0.10
                    ]
                },
            },
        ),
    }
    gates = judge(aggregate(reports))
    assert gates["gate4"]["status"] == "accepted_composite_rank_monotonic_edge"
    assert gates["all_passed"] is True


def test_judge_rejects_inverted_dispersed_component():
    reports = {
        "w1": _report(
            trades=40,
            pit_cov=1.0,
            rank_buckets=[
                _bucket("top_decile", 10),
                _bucket("upper_mid", 30),
            ],
            component_attribution={
                "breadth_alignment": {
                    "buckets": [
                        _bucket("high", 20, avg_r=1.0),
                        _bucket("mid", 20, avg_r=1.7),  # high-low = -0.7 inverted
                    ]
                },
            },
        ),
    }
    gates = judge(aggregate(reports))
    assert gates["gate4"]["status"] == "rejected_composite_rank_inverted"
    assert gates["all_passed"] is False


def test_judge_small_sample_not_clean_monotonic():
    # Dispersed but one bucket below the trade floor -> not clean -> observed.
    reports = {
        "w1": _report(
            trades=40,
            pit_cov=1.0,
            rank_buckets=[_bucket("top_decile", 10), _bucket("upper_mid", 30)],
            component_attribution={
                "theme_participation": {
                    "buckets": [
                        _bucket("mid", 36, avg_r=1.0),
                        _bucket("low", MIN_BUCKET_TRADES - 4, avg_r=2.0),
                    ]
                },
            },
        ),
    }
    gates = judge(aggregate(reports))
    # low bucket below floor -> sample_ok False -> not clean monotonic;
    # rank has a bottom group so not degenerate -> mixed observed_only.
    assert gates["gate4"]["status"] == "observed_only_mixed_no_clean_monotonic_edge"


def test_judge_insufficient_pit_coverage():
    reports = {
        "w1": _report(
            trades=20,
            pit_cov=0.5,  # below floor
            rank_buckets=[_bucket("top_decile", 20)],
            component_attribution={"trend": {"buckets": [_bucket("high", 20)]}},
        ),
    }
    gates = judge(aggregate(reports))
    assert gates["gate4"]["status"] == "observed_only_insufficient_pit_coverage"
    assert gates["gate2"]["passed"] is False
