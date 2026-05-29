"""Unit tests for exp-20260529-007 revision magnitude high-vs-low attribution.

Covers median-split bucketing, horizon stats, decisiveness (bucket-size
floor) detection, and the gate accept / reject / observed-only logic.

No JavaScript was used.
"""

from __future__ import annotations

from quant.experiments.exp_20260529_007_revision_magnitude_high_vs_low_bucket_attribution_7d_and_30d_axes import (  # noqa: E501
    LIFT_FLOOR,
    PUBLISHED_GATE_THRESHOLDS,
    axis_attribution,
    evaluate_gates,
    horizon_stats,
    split_axis,
)


def _row(*, positive=True, delta7=None, delta30=None, ticker="AAPL", r5=None, r10=None):
    return {
        "ticker": ticker,
        "primary_expectation_positive": positive,
        "eps_estimate_delta_7d": delta7,
        "eps_estimate_delta_30d": delta30,
        "forward_outcomes": {
            "5d": {"closed": r5 is not None, "return": r5, "pnl_proxy": (r5 or 0) * 1e4},
            "10d": {"closed": r10 is not None, "return": r10, "pnl_proxy": (r10 or 0) * 1e4},
            "20d": {"closed": False},
        },
    }


def test_split_axis_median_partition():
    rows = [
        _row(delta7=0.01),
        _row(delta7=0.02),
        _row(delta7=0.05),
        _row(delta7=0.10),
        _row(delta7=0.20),
    ]
    split = split_axis(rows, "eps_estimate_delta_7d")
    assert split["positive_row_count"] == 5
    assert split["median_split"] == 0.05
    # high = strictly above median (0.10, 0.20); low = <= median (0.01,0.02,0.05)
    assert len(split["high_magnitude"]) == 2
    assert len(split["low_magnitude"]) == 3


def test_split_axis_ignores_non_positive_and_missing():
    rows = [
        _row(delta7=0.05),
        _row(delta7=-0.05),  # negative -> excluded
        _row(delta7=None),   # missing -> excluded
        _row(delta7=0.0),    # zero (not > 0) -> excluded
        _row(positive=False, delta7=0.10),  # not primary positive -> excluded
    ]
    split = split_axis(rows, "eps_estimate_delta_7d")
    assert split["positive_row_count"] == 1


def test_horizon_stats_empty():
    out = horizon_stats([], "5d")
    assert out["closed_count"] == 0
    assert out["avg_return"] is None


def test_axis_attribution_decisive_flag_requires_both_buckets_meet_floor():
    # 9 high + 9 low rows all closed at 5d -> decisive (>=8 each).
    rows = []
    for i in range(9):
        rows.append(_row(delta7=0.20, ticker=f"H{i}", r5=0.03, r10=0.04))  # high
    for i in range(9):
        rows.append(_row(delta7=0.01, ticker=f"L{i}", r5=0.01, r10=0.01))  # low
    ar = axis_attribution(rows, "eps_estimate_delta_7d", PUBLISHED_GATE_THRESHOLDS)
    assert ar["decisive_by_horizon"]["5d"] is True
    # high beats low at 5d
    assert ar["horizons"]["5d"]["avg_return_lift"] > 0


def test_axis_attribution_not_decisive_when_thin():
    rows = []
    for i in range(3):
        rows.append(_row(delta7=0.20, ticker=f"H{i}", r5=0.03))
    for i in range(3):
        rows.append(_row(delta7=0.01, ticker=f"L{i}", r5=0.01))
    ar = axis_attribution(rows, "eps_estimate_delta_7d", PUBLISHED_GATE_THRESHOLDS)
    assert ar["decisive_by_horizon"]["5d"] is False


def _axis_result(*, lift, decisive, conc=True):
    """Construct a minimal axis_results dict entry for gate testing."""
    return {
        "axis": "eps_estimate_delta_7d",
        "positive_row_count": 20,
        "median_split": 0.05,
        "horizons": {
            "5d": {"avg_return_lift": lift},
            "10d": {"avg_return_lift": 0.0},
        },
        "decisive_by_horizon": {"5d": decisive, "10d": decisive},
        "concentration_passed_by_horizon": {"5d": conc, "10d": conc},
    }


def test_gate4_accepts_when_decisive_axis_lifts_above_floor():
    axis_results = {
        "eps_estimate_delta_7d": _axis_result(lift=0.02, decisive=True, conc=True),
        "eps_estimate_delta_30d": _axis_result(lift=-0.05, decisive=False),
    }
    gates = evaluate_gates(axis_results, rows_total=700)
    assert gates["gate4"]["status"] == "accepted_revision_magnitude_edge"
    assert gates["gate4"]["passed"] is True


def test_gate4_rejects_when_decisive_axis_lift_non_positive():
    axis_results = {
        "eps_estimate_delta_7d": _axis_result(lift=-0.0115, decisive=True, conc=False),
        "eps_estimate_delta_30d": _axis_result(lift=-0.0087, decisive=False),
    }
    gates = evaluate_gates(axis_results, rows_total=700)
    assert gates["gate4"]["status"] == "rejected_no_revision_magnitude_edge"
    assert gates["gate4"]["passed"] is False
    assert gates["gate4"]["decisive_axes"] == ["eps_estimate_delta_7d"]


def test_gate4_observed_only_when_no_axis_decisive():
    axis_results = {
        "eps_estimate_delta_7d": _axis_result(lift=0.02, decisive=False),
        "eps_estimate_delta_30d": _axis_result(lift=0.03, decisive=False),
    }
    gates = evaluate_gates(axis_results, rows_total=700)
    assert gates["gate4"]["status"] == "observed_only_thin_magnitude_buckets"
    assert gates["gate4"]["passed"] is False


def test_gate4_accept_requires_concentration_pass():
    # decisive + positive lift but concentration fails -> not accepted.
    axis_results = {
        "eps_estimate_delta_7d": _axis_result(lift=0.02, decisive=True, conc=False),
    }
    gates = evaluate_gates(axis_results, rows_total=700)
    # decisive axis, lift positive so not "all non-positive" -> observed_only
    assert gates["gate4"]["status"] == "observed_only_thin_magnitude_buckets"


def test_lift_floor_constant():
    assert LIFT_FLOOR == 0.01
