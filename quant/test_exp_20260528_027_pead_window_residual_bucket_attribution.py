"""Unit tests for exp-20260528-027 PEAD window x residual bucket attribution.

Tests cover bucket assignment, per-bucket horizon stats, comparison
diffs, and the gate decision rule (accept / reject / observed-only)
under synthetic enriched rows.

No JavaScript was used.
"""

from __future__ import annotations

from quant.experiments.exp_20260528_027_pead_window_residual_leadership_bucket_attribution_on_enriched_watchlist import (  # noqa: E501
    PUBLISHED_GATE_THRESHOLDS,
    RESIDUAL_LIFT_FLOOR,
    _bucket_horizon_stats,
    assign_pead_bucket,
    comparison_payload,
    evaluate_gates,
)


def _row(
    *,
    primary=True,
    eff_date="2026-05-10",
    last_earnings="2026-05-05",
    pead_window=True,
    residual=True,
    ticker="AAPL",
    forward_5d=None,
    forward_10d=None,
):
    return {
        "ticker": ticker,
        "primary_expectation_positive": primary,
        "watchlist_effective_trade_date": eff_date,
        "last_earnings_date": last_earnings,
        "pead_window": pead_window,
        "residual_leader": residual,
        "forward_outcomes": {
            "5d": forward_5d or {"closed": False},
            "10d": forward_10d or {"closed": False},
            "20d": {"closed": False},
        },
    }


def test_assign_bucket_residual_eligible():
    assert (
        assign_pead_bucket(_row(primary=True, pead_window=True, residual=True))
        == "residual_eligible"
    )


def test_assign_bucket_non_residual_eligible():
    assert (
        assign_pead_bucket(_row(primary=True, pead_window=True, residual=False))
        == "non_residual_eligible"
    )


def test_assign_bucket_outside_window():
    assert (
        assign_pead_bucket(_row(primary=True, pead_window=False, residual=True))
        == "outside_pead_primary_positive"
    )


def test_assign_bucket_missing_last_earnings_date():
    assert (
        assign_pead_bucket(_row(primary=True, last_earnings=None))
        == "blocked_missing_last_earnings_date"
    )


def test_assign_bucket_not_primary():
    assert (
        assign_pead_bucket(_row(primary=False))
        == "not_primary_7d_positive"
    )


def test_bucket_horizon_stats_computes_avg_and_win_rate():
    rows = [
        _row(
            ticker="AAPL",
            forward_5d={"closed": True, "return": 0.02, "pnl_proxy": 200.0},
        ),
        _row(
            ticker="MSFT",
            forward_5d={"closed": True, "return": -0.01, "pnl_proxy": -100.0},
        ),
        _row(
            ticker="GOOG",
            forward_5d={"closed": False, "return": None, "pnl_proxy": None},
        ),
    ]
    out = _bucket_horizon_stats(rows, "5d")
    assert out["row_count"] == 3
    assert out["closed_count"] == 2
    assert out["returns_count"] == 2
    assert out["avg_return"] == 0.005
    assert out["win_rate"] == 0.5
    assert out["total_pnl_proxy"] == 100.0
    assert out["tail_loss"] == -0.01


def test_evaluate_gates_accepts_strong_residual_edge():
    """Synthetic case: residual bucket clearly outperforms with size + concentration ok."""
    stats = {
        "residual_eligible": {
            "row_count": 10,
            "5d": {
                "row_count": 10,
                "closed_count": 10,
                "returns_count": 10,
                "avg_return": 0.05,
                "win_rate": 0.7,
                "total_pnl_proxy": 5000.0,
                "positive_pnl_proxy": 6000.0,
                "tail_loss": -0.01,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
            "10d": {
                "row_count": 10,
                "closed_count": 8,
                "returns_count": 8,
                "avg_return": 0.06,
                "win_rate": 0.75,
                "total_pnl_proxy": 6400.0,
                "positive_pnl_proxy": 7000.0,
                "tail_loss": -0.02,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
        },
        "non_residual_eligible": {
            "row_count": 10,
            "5d": {
                "row_count": 10,
                "closed_count": 10,
                "returns_count": 10,
                "avg_return": 0.01,
                "win_rate": 0.5,
                "total_pnl_proxy": 1000.0,
                "positive_pnl_proxy": 2500.0,
                "tail_loss": -0.02,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
            "10d": {
                "row_count": 10,
                "closed_count": 6,
                "returns_count": 6,
                "avg_return": 0.012,
                "win_rate": 0.5,
                "total_pnl_proxy": 720.0,
                "positive_pnl_proxy": 1500.0,
                "tail_loss": -0.02,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
        },
    }
    comp = comparison_payload(
        name="residual_vs_non_residual_within_pead",
        preferred_bucket="residual_eligible",
        comparison_bucket="non_residual_eligible",
        stats=stats,
        thresholds=PUBLISHED_GATE_THRESHOLDS,
    )
    gates = evaluate_gates([comp], stats, PUBLISHED_GATE_THRESHOLDS)
    assert gates["gate4"]["status"] == "accepted_residual_pead_continuation_edge"
    assert gates["gate4"]["passed"] is True
    assert gates["gate4"]["primary_horizon_lift"] >= RESIDUAL_LIFT_FLOOR


def test_evaluate_gates_rejects_negative_residual_edge():
    """Synthetic case: residual UNDERPERFORMS — the real exp result on enriched data."""
    stats = {
        "residual_eligible": {
            "row_count": 7,
            "5d": {
                "row_count": 7,
                "closed_count": 7,
                "returns_count": 7,
                "avg_return": -0.02,
                "win_rate": 0.43,
                "total_pnl_proxy": -1400.0,
                "positive_pnl_proxy": 200.0,
                "tail_loss": -0.08,
                "top5_positive_share": 1.0,
                "max_single_ticker_positive_share": 0.5,
            },
            "10d": {
                "row_count": 7,
                "closed_count": 7,
                "returns_count": 7,
                "avg_return": 0.025,
                "win_rate": 0.57,
                "total_pnl_proxy": 1750.0,
                "positive_pnl_proxy": 2200.0,
                "tail_loss": -0.04,
                "top5_positive_share": 0.7,
                "max_single_ticker_positive_share": 0.3,
            },
        },
        "non_residual_eligible": {
            "row_count": 8,
            "5d": {
                "row_count": 8,
                "closed_count": 8,
                "returns_count": 8,
                "avg_return": 0.016,
                "win_rate": 0.625,
                "total_pnl_proxy": 1280.0,
                "positive_pnl_proxy": 1500.0,
                "tail_loss": -0.04,
                "top5_positive_share": 0.5,
                "max_single_ticker_positive_share": 0.2,
            },
            "10d": {
                "row_count": 8,
                "closed_count": 4,
                "returns_count": 4,
                "avg_return": 0.018,
                "win_rate": 0.5,
                "total_pnl_proxy": 720.0,
                "positive_pnl_proxy": 1000.0,
                "tail_loss": -0.04,
                "top5_positive_share": 0.5,
                "max_single_ticker_positive_share": 0.2,
            },
        },
    }
    comp = comparison_payload(
        name="residual_vs_non_residual_within_pead",
        preferred_bucket="residual_eligible",
        comparison_bucket="non_residual_eligible",
        stats=stats,
        thresholds=PUBLISHED_GATE_THRESHOLDS,
    )
    gates = evaluate_gates([comp], stats, PUBLISHED_GATE_THRESHOLDS)
    assert gates["gate4"]["status"] == "rejected_no_residual_pead_edge"
    assert gates["gate4"]["passed"] is False
    assert gates["gate4"]["primary_horizon_lift"] < 0


def test_evaluate_gates_observed_only_when_lift_zero_but_size_or_conc_blocks():
    """Synthetic case: lift positive but below floor, or below size floor."""
    stats = {
        "residual_eligible": {
            "row_count": 3,
            "5d": {
                "row_count": 3,
                "closed_count": 3,  # below min_bucket_closed_5d=8
                "returns_count": 3,
                "avg_return": 0.02,
                "win_rate": 0.66,
                "total_pnl_proxy": 600.0,
                "positive_pnl_proxy": 700.0,
                "tail_loss": -0.01,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
            "10d": {
                "row_count": 3,
                "closed_count": 2,
                "returns_count": 2,
                "avg_return": 0.025,
                "win_rate": 0.5,
                "total_pnl_proxy": 500.0,
                "positive_pnl_proxy": 500.0,
                "tail_loss": -0.01,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
        },
        "non_residual_eligible": {
            "row_count": 5,
            "5d": {
                "row_count": 5,
                "closed_count": 5,
                "returns_count": 5,
                "avg_return": 0.01,
                "win_rate": 0.5,
                "total_pnl_proxy": 500.0,
                "positive_pnl_proxy": 600.0,
                "tail_loss": -0.01,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
            "10d": {
                "row_count": 5,
                "closed_count": 3,
                "returns_count": 3,
                "avg_return": 0.012,
                "win_rate": 0.66,
                "total_pnl_proxy": 360.0,
                "positive_pnl_proxy": 400.0,
                "tail_loss": -0.01,
                "top5_positive_share": 0.4,
                "max_single_ticker_positive_share": 0.2,
            },
        },
    }
    comp = comparison_payload(
        name="residual_vs_non_residual_within_pead",
        preferred_bucket="residual_eligible",
        comparison_bucket="non_residual_eligible",
        stats=stats,
        thresholds=PUBLISHED_GATE_THRESHOLDS,
    )
    gates = evaluate_gates([comp], stats, PUBLISHED_GATE_THRESHOLDS)
    # lift positive (+0.01 -> at floor exactly) but bucket size fails for 5d.
    assert gates["gate4"]["status"] == "observed_only_thin_bucket_data_now_available"
    assert gates["gate4"]["passed"] is False


def test_comparison_payload_carries_bucket_size_and_concentration_flags():
    stats = {
        "A": {
            "row_count": 8,
            "5d": {
                "row_count": 8,
                "closed_count": 8,
                "returns_count": 8,
                "avg_return": 0.03,
                "win_rate": 0.6,
                "total_pnl_proxy": 300.0,
                "positive_pnl_proxy": 400.0,
                "tail_loss": -0.01,
                "top5_positive_share": 0.55,  # below max_top5_positive_share=0.6
                "max_single_ticker_positive_share": 0.45,  # below 0.5
            },
            "10d": {
                "row_count": 8,
                "closed_count": 5,
                "returns_count": 5,
                "avg_return": 0.035,
                "win_rate": 0.6,
                "total_pnl_proxy": 280.0,
                "positive_pnl_proxy": 360.0,
                "tail_loss": -0.01,
                "top5_positive_share": 0.55,
                "max_single_ticker_positive_share": 0.45,
            },
        },
        "B": {
            "row_count": 9,
            "5d": {
                "row_count": 9,
                "closed_count": 8,
                "returns_count": 8,
                "avg_return": 0.01,
                "win_rate": 0.5,
                "total_pnl_proxy": 80.0,
                "positive_pnl_proxy": 200.0,
                "tail_loss": -0.01,
                "top5_positive_share": 0.55,
                "max_single_ticker_positive_share": 0.45,
            },
            "10d": {
                "row_count": 9,
                "closed_count": 6,
                "returns_count": 6,
                "avg_return": 0.012,
                "win_rate": 0.5,
                "total_pnl_proxy": 72.0,
                "positive_pnl_proxy": 180.0,
                "tail_loss": -0.01,
                "top5_positive_share": 0.55,
                "max_single_ticker_positive_share": 0.45,
            },
        },
    }
    comp = comparison_payload(
        name="A_vs_B",
        preferred_bucket="A",
        comparison_bucket="B",
        stats=stats,
        thresholds=PUBLISHED_GATE_THRESHOLDS,
    )
    assert comp["bucket_size_floor_passed_by_horizon"]["5d"] is True
    assert comp["bucket_size_floor_passed_by_horizon"]["10d"] is True
    assert comp["concentration_passed_by_horizon"]["5d"] is True
    assert abs(comp["horizons"]["5d"]["avg_return_lift"] - 0.020) < 1e-9
