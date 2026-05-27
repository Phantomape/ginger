from __future__ import annotations

from quant.experiments.exp_20260527_002_expectation_direction_three_round_suite import (
    bucket_candidate_conversion,
    bucket_eps_7d_magnitude,
    bucket_fast_failure,
    bucket_pead_readiness,
    bucket_residual_magnitude,
    bucket_spy_qqq_agreement,
    evaluate_gate,
)
from quant.experiments.exp_20260525_034_expectation_revision_watchlist_attribution import (
    _compact_row,
)


def test_eps_7d_magnitude_requires_primary_positive() -> None:
    assert bucket_eps_7d_magnitude({"eps_estimate_delta_7d": 0.2}) == "not_primary_7d_positive"
    assert (
        bucket_eps_7d_magnitude(
            {"primary_expectation_positive": True, "eps_estimate_delta_7d": 0.12}
        )
        == "primary_7d_high_magnitude"
    )
    assert (
        bucket_eps_7d_magnitude(
            {"primary_expectation_positive": True, "eps_estimate_delta_7d": 0.01}
        )
        == "primary_7d_low_magnitude"
    )


def test_pead_readiness_blocks_missing_earnings_date() -> None:
    assert (
        bucket_pead_readiness(
            {
                "primary_expectation_positive": True,
                "pead_status": "missing_last_earnings_date",
                "residual_leader": True,
            }
        )
        == "blocked_missing_last_earnings_date"
    )
    assert (
        bucket_pead_readiness(
            {
                "primary_expectation_positive": True,
                "pead_status": "inside_t2_t15_after_earnings",
                "residual_leader": True,
            }
        )
        == "eligible_t2_t15_primary_residual"
    )


def test_fast_failure_and_candidate_conversion_buckets() -> None:
    assert (
        bucket_fast_failure(
            {
                "primary_expectation_positive": True,
                "forward_outcomes": {"2d": {"closed": True, "return": -0.03}},
            }
        )
        == "primary_7d_fast_2d_failure"
    )
    assert (
        bucket_fast_failure(
            {
                "primary_expectation_positive": True,
                "forward_outcomes": {"2d": {"closed": True, "return": 0.0}},
            }
        )
        == "primary_7d_no_fast_2d_failure"
    )
    assert (
        bucket_candidate_conversion(
            {
                "primary_expectation_positive": True,
                "candidate_hit_3td": False,
                "candidate_hit_10td": True,
            }
        )
        == "primary_7d_candidate_hit_10td"
    )


def test_residual_buckets_use_available_benchmark_fields() -> None:
    assert (
        bucket_residual_magnitude(
            {
                "primary_expectation_positive": True,
                "residual_strength_score": 0.4,
            }
        )
        == "primary_7d_residual_extreme"
    )
    assert (
        bucket_spy_qqq_agreement(
            {
                "primary_expectation_positive": True,
                "ret20_excess_spy": 0.01,
                "ret20_excess_qqq": -0.01,
            }
        )
        == "primary_7d_leads_only_one_benchmark"
    )


def test_gate_requires_preferred_and_comparison_sample_depth() -> None:
    spec = {
        "preferred_bucket": "preferred",
        "comparison_bucket": "comparison",
    }
    summary = {
        "preferred": {
            "horizons": {
                "5d": {
                    "closed_outcomes": 8,
                    "avg_return": 0.02,
                    "top5_positive_contribution_share": 0.2,
                    "max_single_ticker_positive_share": 0.2,
                },
                "10d": {
                    "closed_outcomes": 5,
                    "avg_return": 0.03,
                },
            }
        },
        "comparison": {
            "horizons": {
                "5d": {"closed_outcomes": 8, "avg_return": -0.01},
                "10d": {"closed_outcomes": 4, "avg_return": -0.02},
            }
        },
    }

    gate = evaluate_gate(spec, summary)
    assert gate["decision"] == "observed_only_data_gap"
    assert "comparison_bucket_closed_outcomes_below_minimum" in gate["data_gap_reasons"]


def test_watchlist_compact_row_preserves_same_event_history_count() -> None:
    compact = _compact_row(
        {
            "as_of_date": "2026-05-20",
            "ticker": "AAPL",
            "same_event_history_count": 13,
            "sector": "Technology",
            "ret20_excess_sector": 0.02,
            "theme_residuals": {"mega_cap": 0.04},
            "themes": ["mega_cap"],
            "candidate_hits": {},
        }
    )

    assert compact["same_event_history_count"] == 13
    assert compact["sector"] == "Technology"
    assert compact["ret20_excess_sector"] == 0.02
    assert compact["ret20_excess_theme"] == 0.04
    assert compact["theme_residuals"] == {"mega_cap": 0.04}
