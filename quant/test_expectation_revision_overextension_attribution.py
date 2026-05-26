from __future__ import annotations

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "experiments"))

from exp_20260526_006_expectation_revision_overextension_attribution import (  # noqa: E402
    AGGREGATE_BUCKETS,
    build_overextension_summary,
    classify_residual_overextension_aggregate,
    classify_residual_overextension_state,
    evaluate_overextension_gate,
    primary_positive_rows,
)


def _row(ticker: str, state: str, ret5: float, ret10: float) -> dict:
    return {
        "ticker": ticker,
        "primary_expectation_positive": True,
        "eps_estimate_delta_7d": 0.01,
        "residual_state": state,
        "revision_residual_overextension_aggregate": classify_residual_overextension_aggregate(
            {"residual_state": state}
        ),
        "forward_outcomes": {
            "5d": {
                "closed": True,
                "return": ret5,
                "pnl_proxy": ret5 * 10000,
                "future_date": "2026-01-08",
            },
            "10d": {
                "closed": True,
                "return": ret10,
                "pnl_proxy": ret10 * 10000,
                "future_date": "2026-01-15",
            },
            "20d": {
                "closed": False,
                "return": None,
                "pnl_proxy": None,
                "future_date": None,
            },
        },
    }


def test_classifies_residual_leaders_as_overextended():
    assert (
        classify_residual_overextension_state({"residual_state": "residual_leader"})
        == "overextended_residual_leader"
    )
    assert (
        classify_residual_overextension_state({"residual_state": "strong_residual_leader"})
        == "overextended_residual_leader"
    )
    assert (
        classify_residual_overextension_state({"residual_state": "neutral"})
        == "neutral_non_overextended"
    )
    assert (
        classify_residual_overextension_state({"residual_state": "beta_lagging"})
        == "beta_lagging_non_overextended"
    )
    assert (
        classify_residual_overextension_aggregate({"residual_state": "neutral"})
        == "non_overextended"
    )


def test_primary_positive_rows_require_strict_7d_pit_positive():
    rows = [
        {"primary_expectation_positive": True, "eps_estimate_delta_7d": 0.01},
        {
            "primary_expectation_positive": False,
            "wide_watchlist_positive": True,
            "eps_estimate_delta_7d": None,
            "eps_estimate_delta_prev": 0.02,
        },
        {"primary_expectation_positive": True, "eps_estimate_delta_7d": 0.0},
        {"primary_expectation_positive": True, "eps_estimate_delta_7d": None},
    ]

    assert primary_positive_rows(rows) == [rows[0]]


def test_gate_passes_direction_when_non_overextended_beats_leaders():
    rows = []
    for idx in range(15):
        rows.append(_row(f"N{idx}", "neutral", 0.02, 0.03))
    for idx in range(15):
        rows.append(_row(f"L{idx}", "residual_leader", -0.01, -0.02))

    summary = build_overextension_summary(
        rows,
        bucket_key="revision_residual_overextension_aggregate",
        bucket_order=AGGREGATE_BUCKETS,
    )
    gate = evaluate_overextension_gate(summary, len(rows))

    assert gate["directional_passed"] is True
    assert gate["promotion_gate_passed"] is True
    assert gate["decision"] == "observed_only_promising_overextension_guard"
