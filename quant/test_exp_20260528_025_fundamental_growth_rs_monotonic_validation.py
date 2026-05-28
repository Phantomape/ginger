from __future__ import annotations

from quant.experiments.exp_20260528_025_fundamental_growth_rs_monotonic_rank_validation import (
    assign_score_terciles,
    monotonicity_report,
    summarize_score_buckets,
)


def test_score_terciles_are_count_based_descending():
    rows = [{"score": float(score), "pnl": 1.0, "paper_notional_usd": 100.0} for score in range(9)]

    bucketed = assign_score_terciles(rows)
    buckets_by_score = {row["score"]: row["score_bucket"] for row in bucketed}

    assert buckets_by_score[8.0] == "top_tercile"
    assert buckets_by_score[4.0] == "middle_tercile"
    assert buckets_by_score[0.0] == "bottom_tercile"


def test_monotonicity_report_requires_overall_and_window_stability():
    rows = []
    for window in ("late_strong", "mid_weak", "old_thin"):
        rows.extend(
            [
                {"window": window, "score": 0.9, "pnl": 30.0, "paper_notional_usd": 100.0},
                {"window": window, "score": 0.8, "pnl": 25.0, "paper_notional_usd": 100.0},
                {"window": window, "score": 0.7, "pnl": 20.0, "paper_notional_usd": 100.0},
                {"window": window, "score": 0.6, "pnl": 10.0, "paper_notional_usd": 100.0},
                {"window": window, "score": 0.5, "pnl": 8.0, "paper_notional_usd": 100.0},
                {"window": window, "score": 0.4, "pnl": 6.0, "paper_notional_usd": 100.0},
                {"window": window, "score": 0.3, "pnl": -1.0, "paper_notional_usd": 100.0},
                {"window": window, "score": 0.2, "pnl": -2.0, "paper_notional_usd": 100.0},
                {"window": window, "score": 0.1, "pnl": -3.0, "paper_notional_usd": 100.0},
            ]
        )

    overall = summarize_score_buckets(rows)
    by_window = {
        window: summarize_score_buckets([row for row in rows if row["window"] == window])
        for window in ("late_strong", "mid_weak", "old_thin")
    }
    report = monotonicity_report(overall, by_window)

    assert report["passed_observed_only_validation"] is True
    assert set(report["monotonic_windows"]) == {"late_strong", "mid_weak", "old_thin"}
