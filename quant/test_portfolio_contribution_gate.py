"""Tests for the independent portfolio-contribution evaluation lane."""

from __future__ import annotations

from copy import deepcopy

import pytest

from quant.evaluator_gates import (
    evaluate_experiment_promotion_gate,
    evaluate_portfolio_contribution_gate,
)


def _window(
    *,
    core_ev: float,
    ev_delta: float,
    pnl_delta: float,
) -> dict[str, float]:
    return {
        "core_ev": core_ev,
        "ev_delta": ev_delta,
        "pnl_delta": pnl_delta,
    }


def _pass_metrics(**overrides):
    metrics = {
        "capital_neutral": True,
        "candidate_weight": 0.10,
        "core_weight": 0.90,
        "portfolio_weight_sum": 1.0,
        "aggregate_ev_delta": 0.08,
        "aggregate_pnl_delta": 1200.0,
        "affected_trade_count": 24,
        "affected_window_count": 3,
        "window_contributions": {
            "late_strong": _window(core_ev=6.0, ev_delta=0.04, pnl_delta=500.0),
            "mid_weak": _window(core_ev=4.0, ev_delta=0.03, pnl_delta=400.0),
            "old_thin": _window(core_ev=1.0, ev_delta=0.01, pnl_delta=300.0),
        },
        "max_drawdown_worse": 0.004,
        "es95_worsening_fraction": 0.04,
        "single_ticker_positive_share": 0.40,
        "top_5_contribution_pct": 0.55,
        "hhi_concentration": 0.25,
        "family_batch_complete": True,
        "expected_family_count": 31,
        "observed_family_count": 31,
        "selection_panel_complete": True,
        "multiple_testing_passed": True,
        "simultaneous_ev_delta_lower_bound": 0.002,
    }
    metrics.update(overrides)
    return metrics


def test_portfolio_gate_accepts_complete_capital_neutral_evidence():
    report = evaluate_portfolio_contribution_gate(_pass_metrics())

    assert report["passed"] is True
    assert report["status"] == "passed"
    assert report["portfolio_verdict"] == "accepted_portfolio_paper"
    assert report["hard_failures"] == []
    assert report["evidence_blockers"] == []
    assert report["checks"]["material_window_regression_guard"] is True


def test_portfolio_gate_is_read_only():
    metrics = _pass_metrics()
    before = deepcopy(metrics)

    evaluate_portfolio_contribution_gate(metrics)

    assert metrics == before


@pytest.mark.parametrize(
    ("key", "value", "failure"),
    [
        ("aggregate_ev_delta", 0.0, "non_positive_aggregate_ev"),
        ("aggregate_pnl_delta", -1.0, "non_positive_aggregate_pnl"),
        ("candidate_weight", 0.100001, "candidate_weight_cap"),
        ("max_drawdown_worse", 0.005001, "drawdown_worse_guardrail"),
        ("es95_worsening_fraction", 0.050001, "es95_worse_guardrail"),
    ],
)
def test_portfolio_gate_rejects_observed_economic_or_risk_breach(
    key,
    value,
    failure,
):
    report = evaluate_portfolio_contribution_gate(_pass_metrics(**{key: value}))

    assert report["portfolio_verdict"] == "portfolio_reject"
    assert failure in report["hard_failures"]


def test_portfolio_gate_accepts_inclusive_weight_drawdown_and_es95_caps():
    report = evaluate_portfolio_contribution_gate(
        _pass_metrics(
            candidate_weight=0.10,
            max_drawdown_worse=0.005,
            es95_worsening_fraction=0.05,
        )
    )

    assert report["portfolio_verdict"] == "accepted_portfolio_paper"


def test_portfolio_gate_requires_the_locked_90_10_capital_mix():
    report = evaluate_portfolio_contribution_gate(
        _pass_metrics(
            candidate_weight=0.05,
            core_weight=0.95,
            portfolio_weight_sum=1.0,
        )
    )

    assert report["portfolio_verdict"] == "portfolio_forward_watch"
    assert "candidate_weight_not_fixed" in report["measurement_blockers"]
    assert "core_weight_not_fixed" in report["measurement_blockers"]
    assert report["checks"]["fixed_capital_weights"] is False


@pytest.mark.parametrize(
    ("key", "value", "failure"),
    [
        (
            "single_ticker_positive_share",
            0.500001,
            "single_ticker_positive_share_cap",
        ),
        ("top_5_contribution_pct", 0.600001, "top_5_contribution_pct_cap"),
        ("hhi_concentration", 0.350001, "hhi_concentration_cap"),
    ],
)
def test_portfolio_gate_rejects_concentration_cap_breach(key, value, failure):
    report = evaluate_portfolio_contribution_gate(_pass_metrics(**{key: value}))

    assert report["portfolio_verdict"] == "portfolio_reject"
    assert failure in report["hard_failures"]


def test_portfolio_gate_accepts_concentration_values_at_caps():
    report = evaluate_portfolio_contribution_gate(
        _pass_metrics(
            single_ticker_positive_share=0.50,
            top_5_contribution_pct=0.60,
            hhi_concentration=0.35,
        )
    )

    assert report["portfolio_verdict"] == "accepted_portfolio_paper"


def test_sub_one_percent_ev_loss_is_noise_even_when_window_pnl_is_negative():
    windows = deepcopy(_pass_metrics()["window_contributions"])
    windows["old_thin"] = _window(
        core_ev=100.0,
        ev_delta=-0.99,
        pnl_delta=-100.0,
    )

    report = evaluate_portfolio_contribution_gate(
        _pass_metrics(window_contributions=windows)
    )

    assert report["portfolio_verdict"] == "accepted_portfolio_paper"
    old_thin = next(
        row for row in report["window_checks"] if row["window"] == "old_thin"
    )
    assert old_thin["material_regression"] is False


def test_negative_ev_window_with_nonnegative_pnl_is_not_material_regression():
    windows = deepcopy(_pass_metrics()["window_contributions"])
    windows["old_thin"] = _window(
        core_ev=1.0,
        ev_delta=-0.20,
        pnl_delta=57.0,
    )

    report = evaluate_portfolio_contribution_gate(
        _pass_metrics(window_contributions=windows)
    )

    assert report["portfolio_verdict"] == "accepted_portfolio_paper"
    assert report["metrics"]["material_regressed_windows"] == 0


def test_exactly_one_percent_ev_loss_is_not_material_under_strict_contract():
    windows = deepcopy(_pass_metrics()["window_contributions"])
    windows["old_thin"] = _window(
        core_ev=100.0,
        ev_delta=-1.0,
        pnl_delta=-100.0,
    )

    report = evaluate_portfolio_contribution_gate(
        _pass_metrics(window_contributions=windows)
    )

    assert report["portfolio_verdict"] == "accepted_portfolio_paper"
    assert report["metrics"]["material_regressed_windows"] == 0


def test_two_material_regressions_reject_portfolio_candidate():
    windows = {
        "late_strong": _window(core_ev=100.0, ev_delta=-2.0, pnl_delta=-200.0),
        "mid_weak": _window(core_ev=100.0, ev_delta=-1.01, pnl_delta=-100.0),
        "old_thin": _window(core_ev=1.0, ev_delta=0.1, pnl_delta=1500.0),
    }

    report = evaluate_portfolio_contribution_gate(
        _pass_metrics(window_contributions=windows)
    )

    assert report["portfolio_verdict"] == "portfolio_reject"
    assert "too_many_material_regressed_windows" in report["hard_failures"]
    assert "insufficient_non_regressed_windows" in report["hard_failures"]


def test_known_hard_regressions_still_reject_when_another_window_is_incomplete():
    windows = {
        "late_strong": _window(core_ev=100.0, ev_delta=-2.0, pnl_delta=-200.0),
        "mid_weak": _window(core_ev=100.0, ev_delta=-1.01, pnl_delta=-100.0),
        "old_thin": {"core_ev": 1.0, "ev_delta": 0.1},
    }

    report = evaluate_portfolio_contribution_gate(
        _pass_metrics(window_contributions=windows, affected_window_count=3)
    )

    assert report["portfolio_verdict"] == "portfolio_reject"
    assert "too_many_material_regressed_windows" in report["hard_failures"]
    assert "invalid_window_contribution:old_thin" in report["evidence_blockers"]


@pytest.mark.parametrize(
    ("overrides", "blocker"),
    [
        ({"capital_neutral": False}, "capital_not_neutral"),
        ({"affected_trade_count": 19}, "insufficient_affected_sample"),
        ({"selection_panel_complete": False}, "selection_panel_incomplete"),
        ({"multiple_testing_passed": False}, "multiple_testing_not_passed"),
        (
            {"simultaneous_ev_delta_lower_bound": 0.0},
            "simultaneous_ev_lower_bound_not_positive",
        ),
    ],
)
def test_incomplete_measurement_or_statistical_evidence_goes_to_forward_watch(
    overrides,
    blocker,
):
    report = evaluate_portfolio_contribution_gate(_pass_metrics(**overrides))

    assert report["passed"] is False
    assert report["portfolio_verdict"] == "portfolio_forward_watch"
    assert report["hard_failures"] == []
    assert blocker in report["evidence_blockers"]


@pytest.mark.parametrize(
    ("overrides", "blocker"),
    [
        ({"family_batch_complete": False}, "family_batch_incomplete"),
        ({"observed_family_count": 30}, "family_count_mismatch"),
        ({"expected_family_count": 30}, "unexpected_family_batch_scope"),
    ],
)
def test_family_batch_completeness_is_independent_from_selection_panel(
    overrides,
    blocker,
):
    report = evaluate_portfolio_contribution_gate(_pass_metrics(**overrides))

    assert report["portfolio_verdict"] == "portfolio_forward_watch"
    assert report["checks"]["selection_panel_complete"] is True
    assert report["checks"]["family_batch_complete"] is False
    assert blocker in report["statistical_blockers"]


@pytest.mark.parametrize(
    ("missing_key", "blocker"),
    [
        ("aggregate_ev_delta", "missing_aggregate_ev_delta"),
        ("max_drawdown_worse", "missing_drawdown_delta"),
        ("es95_worsening_fraction", "missing_es95_worsening_fraction"),
        ("hhi_concentration", "missing_hhi_concentration"),
        (
            "simultaneous_ev_delta_lower_bound",
            "missing_simultaneous_ev_delta_lower_bound",
        ),
    ],
)
def test_missing_evidence_goes_to_forward_watch(missing_key, blocker):
    metrics = _pass_metrics()
    metrics.pop(missing_key)

    report = evaluate_portfolio_contribution_gate(metrics)

    assert report["portfolio_verdict"] == "portfolio_forward_watch"
    assert blocker in report["evidence_blockers"]


def test_window_count_mismatch_and_incomplete_window_metrics_are_watch_blockers():
    windows = deepcopy(_pass_metrics()["window_contributions"])
    windows["old_thin"].pop("pnl_delta")

    report = evaluate_portfolio_contribution_gate(
        _pass_metrics(window_contributions=windows, affected_window_count=3)
    )

    assert report["portfolio_verdict"] == "portfolio_forward_watch"
    assert "invalid_window_contribution:old_thin" in report["measurement_blockers"]
    assert "affected_window_count_mismatch" in report["measurement_blockers"]


def test_only_one_non_regressed_window_fails_portfolio_economics():
    windows = {
        "late_strong": _window(core_ev=100.0, ev_delta=-1.01, pnl_delta=-100.0),
        "mid_weak": _window(core_ev=1.0, ev_delta=0.2, pnl_delta=1300.0),
    }

    report = evaluate_portfolio_contribution_gate(
        _pass_metrics(window_contributions=windows, affected_window_count=2)
    )

    assert report["portfolio_verdict"] == "portfolio_reject"
    assert "insufficient_non_regressed_windows" in report["hard_failures"]


def test_existing_champion_promotion_gate_contract_is_unchanged():
    metrics = {
        "aggregate_ev_delta": 0.25,
        "aggregate_pnl_delta": 2500.0,
        "windows_ev_improved": 2,
        "windows_ev_regressed": 1,
        "adjusted_trade_count": 12,
        "adjusted_windows": ["late_strong", "mid_weak"],
        "max_drawdown_worse_max": 0.001,
        "single_ticker_positive_share": 0.32,
        "baseline_single_ticker_positive_share": 0.38,
        "pnl_top_5_contribution_pct": 0.46,
        "baseline_pnl_top_5_contribution_pct": 0.52,
        "pnl_hhi_concentration": 0.16,
        "baseline_pnl_hhi_concentration": 0.19,
    }

    report = evaluate_experiment_promotion_gate(metrics)

    assert report["passed"] is False
    assert "ev_regressed_windows" in report["hard_failures"]
