from __future__ import annotations

from quant.experiments.exp_20260526_030_expectation_direction_untried_ideas_suite import (
    assign_rank_buckets,
    attribution_metric_completeness,
    classify_pead_bucket,
    classify_revision_velocity_bucket,
    classify_surprise_guidance_bucket,
    expectation_residual_component_score,
    extract_earnings_snapshot_rows,
    field_coverage,
)


def test_revision_velocity_bucket_requires_primary_7d_positive() -> None:
    assert classify_revision_velocity_bucket({"eps_estimate_delta_7d": 0.2}) == "not_primary_positive_7d"
    assert (
        classify_revision_velocity_bucket(
            {
                "primary_expectation_positive": True,
                "eps_estimate_delta_7d": 0.2,
                "eps_estimate_delta_30d": None,
            }
        )
        == "primary_7d_missing_30d_velocity"
    )
    assert (
        classify_revision_velocity_bucket(
            {
                "primary_expectation_positive": True,
                "eps_estimate_delta_7d": 0.3,
                "eps_estimate_delta_30d": 0.1,
            }
        )
        == "primary_7d_30d_positive_accelerating"
    )


def test_pead_bucket_blocks_missing_last_earnings_date() -> None:
    assert (
        classify_pead_bucket(
            {
                "primary_expectation_positive": True,
                "pead_status": "missing_last_earnings_date",
            }
        )
        == "blocked_missing_last_earnings_date"
    )
    assert (
        classify_pead_bucket(
            {
                "primary_expectation_positive": True,
                "pead_status": "inside_t2_t15_after_earnings",
                "residual_leader": False,
            }
        )
        == "eligible_primary_positive_non_residual_leader"
    )


def test_extract_earnings_snapshot_rows_handles_dict_and_list_shapes() -> None:
    dict_payload = {"earnings": {"aapl": {"avg_historical_surprise_pct": 1.2}}}
    list_payload = {"earnings": [{"ticker": "msft", "avg_historical_surprise_pct": 2.3}]}

    assert extract_earnings_snapshot_rows(dict_payload)["AAPL"]["avg_historical_surprise_pct"] == 1.2
    assert extract_earnings_snapshot_rows(list_payload)["MSFT"]["avg_historical_surprise_pct"] == 2.3


def test_surprise_guidance_bucket_prefers_current_fields_over_history() -> None:
    assert (
        classify_surprise_guidance_bucket(
            {
                "primary_expectation_positive": True,
                "guidance_value": "positive",
                "avg_historical_surprise_pct": -1.0,
            }
        )
        == "primary_positive_revision_guidance_available"
    )
    assert (
        classify_surprise_guidance_bucket(
            {
                "primary_expectation_positive": True,
                "current_surprise_value": 3.0,
                "avg_historical_surprise_pct": -1.0,
            }
        )
        == "primary_positive_revision_current_surprise_positive"
    )
    assert (
        classify_surprise_guidance_bucket(
            {
                "primary_expectation_positive": True,
                "avg_historical_surprise_pct": 4.0,
            }
        )
        == "primary_positive_revision_positive_surprise_history_proxy"
    )


def test_rank_component_assigns_top_and_bottom_buckets() -> None:
    rows = []
    for idx in range(20):
        rows.append(
            {
                "ticker": f"T{idx}",
                "as_of_date": "2026-05-20",
                "expectation_residual_component_score": float(idx),
            }
        )

    ranked = assign_rank_buckets(rows)
    assert [row["expectation_residual_component_rank_bucket"] for row in ranked[:2]] == [
        "top_decile",
        "top_decile",
    ]
    assert ranked[-1]["expectation_residual_component_rank_bucket"] == "bottom_quintile"


def test_component_score_excludes_feature_only_rows_without_signals() -> None:
    feature_only = {"ticker": "AAPL", "residual_leader": False}
    signal_row = {"ticker": "AAPL", "primary_expectation_positive": True, "residual_leader": True}

    assert expectation_residual_component_score(feature_only) == 0.0
    assert expectation_residual_component_score(signal_row) == 1.5


def test_field_coverage_and_metric_completeness_report_missing_promotion_metrics() -> None:
    rows = [
        {
            "ticker": "AAPL",
            "ret20_excess_spy": 0.1,
            "forward_outcomes": {
                "5d": {"closed": True, "return": 0.02, "pnl_proxy": 200.0},
            },
        },
        {"ticker": "MSFT", "forward_outcomes": {"5d": {"closed": False}}},
    ]

    coverage = field_coverage(rows, ["ret20_excess_spy", "ret20_excess_sector"])
    assert coverage["ret20_excess_spy"]["present_rows"] == 1
    assert coverage["ret20_excess_sector"]["present_rows"] == 0

    completeness = attribution_metric_completeness(rows)
    assert completeness["available_metrics"]["avg_return"]["available"] is True
    assert completeness["missing_promotion_metrics"]["avg_R"]["available"] is False
