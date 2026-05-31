"""Unit tests for exp-20260531-006 full-universe quantile forward-return judge.

Covers forward-return computation, quantile bucketing, ladder monotonicity
detection, and the gate decision branches: clean monotonic accept,
top-vs-bottom edge without clean ladder, inversion reject, insufficient
observations, and no-edge observed-only.

No JavaScript was used.
"""

from __future__ import annotations

import pandas as pd

from quant.experiments.exp_20260531_006_full_universe_alpha_score_quantile_forward_return import (  # noqa: E501
    EDGE_FLOOR,
    MIN_BUCKET_OBS,
    _forward_returns,
    aggregate,
    judge,
    quantile_attribution,
)


def _frame(closes, start="2025-01-02"):
    idx = pd.bdate_range(start=start, periods=len(closes))
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1] * len(closes),
        },
        index=idx,
    )


def test_forward_returns_basic():
    closes = [100.0] + [None] * 0
    closes = [100, 101, 102, 103, 104, 110, 100, 100, 100, 100, 100, 120]
    frame = _frame([float(c) for c in closes])
    asof = frame.index[0]
    fwd = _forward_returns(frame, asof)
    # 5d -> index 5 -> 110 -> +10%; 10d -> index 10 -> 100 -> 0%
    assert abs(fwd[5] - 0.10) < 1e-9
    assert abs(fwd[10] - 0.0) < 1e-9


def test_forward_returns_missing_when_no_exact_bar():
    frame = _frame([100.0, 101.0, 102.0])
    # a timestamp not in the index
    fwd = _forward_returns(frame, pd.Timestamp("2030-01-01"))
    assert fwd == {}


def _obs(alpha, r5, r10=0.0, r20=0.0, ticker="T"):
    return {
        "asof_date": "2025-06-01",
        "ticker": ticker,
        "alpha_score": alpha,
        "forward_returns": {5: r5, 10: r10, 20: r20},
    }


def test_quantile_attribution_monotonic_ladder_detected():
    # 5 buckets, strictly increasing 5d returns by alpha rank.
    obs = []
    for q in range(5):
        for _ in range(40):
            obs.append(_obs(alpha=0.1 * q, r5=0.01 * q))
    qa = quantile_attribution(obs, 5, "q")
    assert qa["monotonic_increasing_ladder"]["h5"] is True
    assert qa["top_minus_bottom_spread"]["h5"] > 0


def test_quantile_attribution_non_monotonic_flagged():
    # bottom bucket beats middle -> not monotonic, but top > bottom.
    pattern = [0.02, 0.005, 0.004, 0.006, 0.03]  # Q1..Q5 5d avg
    obs = []
    for q, r in enumerate(pattern):
        for _ in range(40):
            obs.append(_obs(alpha=0.1 * q, r5=r))
    qa = quantile_attribution(obs, 5, "q")
    assert qa["monotonic_increasing_ladder"]["h5"] is False
    assert qa["top_minus_bottom_spread"]["h5"] > 0  # 0.03 - 0.02 > 0


def _per_window_pattern(patterns):
    """Build per-window observation sets from explicit Q1..Q5 5d patterns."""
    per = {}
    for w, pattern in patterns.items():
        obs = []
        for q, r in enumerate(pattern):
            for _ in range(40):
                obs.append(_obs(alpha=0.1 * q, r5=r))
        per[w] = obs
    return per


def test_judge_observed_only_without_clean_ladder():
    # top > bottom in every window, but the pooled ladder is non-monotonic
    # (Q1 beats Q2/Q3) -> observed_only_top_bottom_edge_without_clean_ladder.
    # This mirrors the real exp-20260531-006 shape.
    pat = [0.02, 0.005, 0.004, 0.006, 0.03]  # Q1..Q5; top-bottom = +0.01
    per = _per_window_pattern({"a": pat, "b": pat, "c": pat})
    agg = aggregate(per)
    gates = judge(agg)
    assert gates["gate4"]["status"] == "observed_only_top_bottom_edge_without_clean_ladder"
    assert gates["all_passed"] is False


def test_judge_reject_when_inverted():
    # top bucket strictly worse than bottom in every window -> pooled spread
    # negative -> reject.
    pat = [0.03, 0.01, 0.0, -0.01, -0.02]  # Q5 - Q1 = -0.05
    per = _per_window_pattern({"a": pat, "b": pat, "c": pat})
    agg = aggregate(per)
    gates = judge(agg)
    assert gates["gate4"]["status"] == "rejected_full_universe_alpha_score_inverted"


def test_judge_accept_clean_monotonic_majority_positive():
    # Build a strictly increasing ladder in every window.
    per = {}
    for w in ("a", "b", "c"):
        obs = []
        for q in range(5):
            for _ in range(40):
                obs.append(_obs(alpha=0.1 * q, r5=0.01 * q))
        per[w] = obs
    agg = aggregate(per)
    gates = judge(agg)
    assert gates["gate4"]["status"] == "accepted_full_universe_alpha_score_forward_edge"
    assert gates["all_passed"] is True


def test_judge_insufficient_observations():
    per = {"a": [_obs(alpha=0.1 * q, r5=0.01) for q in range(5)]}  # 5 obs total
    agg = aggregate(per)
    gates = judge(agg)
    assert gates["gate4"]["status"] == "observed_only_insufficient_universe_observations"
    assert gates["gate2"]["passed"] is False


def test_constants():
    assert EDGE_FLOOR == 0.005
    assert MIN_BUCKET_OBS == 30
