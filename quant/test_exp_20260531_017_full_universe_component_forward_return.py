"""Tests for exp-20260531-016 component-level ranking attribution.

No JavaScript was used.
"""

from __future__ import annotations

from quant.experiments.exp_20260531_017_full_universe_alpha_score_component_forward_return import (
    EDGE_FLOOR,
    MIN_BUCKET_OBS,
    aggregate,
    component_quantile_attribution,
    judge,
)


def _obs(component: str, score: float, r5: float, ticker: str = "T") -> dict:
    component_scores = {
        "trend": 0.1,
        "relative_strength": 0.1,
        "expectation_revision": 0.1,
        "post_earnings_drift": 0.1,
        "theme_participation": 0.1,
        "breadth_alignment": 0.1,
    }
    component_scores[component] = score
    return {
        "asof_date": "2025-06-01",
        "ticker": ticker,
        "alpha_score": score,
        "component_scores": component_scores,
        "forward_returns": {5: r5, 10: r5, 20: r5},
    }


def _per_window(component: str, patterns: dict[str, list[float]]) -> dict[str, list[dict]]:
    per = {}
    for window, bucket_returns in patterns.items():
        rows = []
        for bucket, ret in enumerate(bucket_returns):
            for i in range(40):
                rows.append(
                    _obs(
                        component,
                        score=float(bucket),
                        r5=ret,
                        ticker=f"{window}_{bucket}_{i}",
                    )
                )
        per[window] = rows
    return per


def test_component_quantile_attribution_detects_clean_ladder():
    rows = []
    for bucket in range(5):
        for i in range(40):
            rows.append(_obs("breadth_alignment", float(bucket), 0.01 * bucket, f"T{bucket}_{i}"))

    attr = component_quantile_attribution(rows, "breadth_alignment")

    assert attr["monotonic_increasing_ladder"]["h5"] is True
    assert attr["top_minus_bottom_spread"]["h5"] >= EDGE_FLOOR
    assert min(bucket["n_obs"] for bucket in attr["buckets"]) >= MIN_BUCKET_OBS


def test_judge_observed_only_for_non_ohlcv_component_pass():
    patterns = {
        "late_strong": [0.0, 0.01, 0.02, 0.03, 0.04],
        "mid_weak": [0.0, 0.01, 0.02, 0.03, 0.04],
        "old_thin": [0.0, 0.01, 0.02, 0.03, 0.04],
    }
    gates = judge(aggregate(_per_window("breadth_alignment", patterns)))

    assert gates["gate4"]["status"] == "observed_only_component_monotonic_candidate"
    assert gates["all_passed"] is True


def test_judge_blocks_existing_ohlcv_remix_pass():
    patterns = {
        "late_strong": [0.0, 0.01, 0.02, 0.03, 0.04],
        "mid_weak": [0.0, 0.01, 0.02, 0.03, 0.04],
        "old_thin": [0.0, 0.01, 0.02, 0.03, 0.04],
    }
    gates = judge(aggregate(_per_window("relative_strength", patterns)))

    assert gates["gate4"]["status"] == "observed_only_component_edge_existing_ohlcv_remix"
    assert gates["all_passed"] is False


def test_judge_rejects_non_monotonic_component_set():
    pattern = [0.02, 0.00, 0.01, 0.005, 0.03]
    gates = judge(
        aggregate(
            _per_window(
                "breadth_alignment",
                {"late_strong": pattern, "mid_weak": pattern, "old_thin": pattern},
            )
        )
    )

    assert gates["gate4"]["status"] == "observed_only_component_edge_without_clean_ladder"
    assert gates["all_passed"] is False
