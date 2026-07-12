"""Deterministic tests for Bailey--Lopez de Prado Sharpe inference."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import statistics

import pytest

from quant.sharpe_inference import (
    build_backtest_sharpe_inference,
    deflated_sharpe_ratio,
    evaluate_deflated_sharpe_trial_panel,
    expected_maximum_sharpe,
    probabilistic_sharpe_ratio,
)


def test_psr_normal_moment_vector_and_symmetry() -> None:
    positive = probabilistic_sharpe_ratio(
        observed_sharpe_periodic=0.1,
        benchmark_sharpe_periodic=0.0,
        sample_count=252,
        skewness=0.0,
        pearson_kurtosis=3.0,
    )
    negative = probabilistic_sharpe_ratio(
        observed_sharpe_periodic=-0.1,
        benchmark_sharpe_periodic=0.0,
        sample_count=252,
        skewness=0.0,
        pearson_kurtosis=3.0,
    )

    assert positive["status"] == "computable"
    assert positive["probability"] == pytest.approx(
        0.9429868610243622, abs=1e-15
    )
    assert negative["probability"] == pytest.approx(
        0.057013138975637756, abs=1e-15
    )
    assert positive["probability"] + negative["probability"] == pytest.approx(1.0)


def test_psr_is_one_half_at_the_benchmark() -> None:
    result = probabilistic_sharpe_ratio(
        observed_sharpe_periodic=0.17,
        benchmark_sharpe_periodic=0.17,
        sample_count=411,
        skewness=-1.2,
        pearson_kurtosis=7.5,
    )
    assert result["status"] == "computable"
    assert result["z_score"] == 0.0
    assert result["probability"] == 0.5


def test_psr_requires_pearson_not_fisher_kurtosis() -> None:
    result = probabilistic_sharpe_ratio(
        observed_sharpe_periodic=0.1,
        benchmark_sharpe_periodic=0.0,
        sample_count=252,
        skewness=0.0,
        pearson_kurtosis=0.0,
    )
    assert result == {
        "status": "not_computable",
        "reason_codes": ["pearson_kurtosis_below_theoretical_minimum"],
    }


def test_psr_rejects_inconsistent_nonpositive_asymptotic_variance() -> None:
    result = probabilistic_sharpe_ratio(
        observed_sharpe_periodic=1.0,
        benchmark_sharpe_periodic=0.0,
        sample_count=100,
        skewness=5.0,
        pearson_kurtosis=1.0,
    )
    assert result["status"] == "not_computable"
    assert result["reason_codes"] == [
        "sharpe_asymptotic_variance_not_positive"
    ]


@pytest.mark.parametrize(
    ("trial_count", "expected_z"),
    [
        (2, 0.5197553442793358),
        (10, 1.5745983013452856),
        (100, 2.5306028932016846),
        (1000, 3.255121513653265),
    ],
)
def test_expected_maximum_standard_normal_vectors(
    trial_count: int, expected_z: float
) -> None:
    result = expected_maximum_sharpe(
        trial_sharpe_std_periodic=1.0,
        independent_trial_count=trial_count,
    )
    assert result["status"] == "computable"
    assert result["extreme_value_z"] == pytest.approx(expected_z, abs=2e-12)
    assert result["expected_maximum_sharpe_periodic"] == pytest.approx(
        expected_z, abs=2e-12
    )


def test_expected_maximum_single_trial_special_case_does_not_need_dispersion() -> None:
    result = expected_maximum_sharpe(
        trial_sharpe_std_periodic=None,
        independent_trial_count=1,
    )
    assert result["status"] == "computable"
    assert result["expected_maximum_sharpe_periodic"] == 0.0
    assert result["extreme_value_z"] == 0.0
    assert result["method"] == "single_trial_zero_skill_null"


def test_expected_maximum_fails_closed_without_dispersion_for_multiple_trials() -> None:
    result = expected_maximum_sharpe(
        trial_sharpe_std_periodic=None,
        independent_trial_count=2,
    )
    assert result["status"] == "not_computable"
    assert result["reason_codes"] == ["missing_or_invalid_trial_sharpe_std"]


def test_expected_maximum_fails_closed_when_fractional_n_breaks_large_n_approximation() -> None:
    result = expected_maximum_sharpe(
        trial_sharpe_std_periodic=0.2,
        independent_trial_count=1.1,
    )
    assert result["status"] == "not_computable"
    assert result["reason_codes"] == ["expected_maximum_approximation_negative"]
    assert result["extreme_value_z"] < 0.0


def _paper_dsr(*, periods_per_year: int, trials: int, skew: float, kurt: float):
    return deflated_sharpe_ratio(
        observed_sharpe_periodic=2.5 / math.sqrt(periods_per_year),
        sample_count=1250,
        skewness=skew,
        pearson_kurtosis=kurt,
        trial_sharpe_std_periodic=math.sqrt(0.5 / periods_per_year),
        independent_trial_count=trials,
    )


def test_dsr_published_250_period_n100_gold_vector() -> None:
    result = _paper_dsr(periods_per_year=250, trials=100, skew=-3.0, kurt=10.0)
    assert result["status"] == "computable"
    assert result["expected_maximum_sharpe_periodic"] * math.sqrt(250) == pytest.approx(
        1.789406466272824, abs=5e-13
    )
    assert result["probability"] == pytest.approx(
        0.9003968344495116, abs=5e-13
    )
    # This catches the common bug of putting SR0, rather than observed SR,
    # into the higher-moment variance denominator.
    assert result["asymptotic_variance_numerator"] == pytest.approx(
        1.530591649025257, abs=1e-15
    )


def test_dsr_published_250_period_n46_boundary_vector() -> None:
    result = _paper_dsr(periods_per_year=250, trials=46, skew=-3.0, kurt=10.0)
    assert result["status"] == "computable"
    assert result["probability"] == pytest.approx(
        0.9505017068756568, abs=5e-13
    )


def test_dsr_published_normal_moment_n88_vector() -> None:
    result = _paper_dsr(periods_per_year=250, trials=88, skew=0.0, kurt=3.0)
    assert result["status"] == "computable"
    assert result["probability"] == pytest.approx(
        0.9504908166761022, abs=5e-13
    )


def test_dsr_warehouse_252_period_gold_vector() -> None:
    result = _paper_dsr(periods_per_year=252, trials=100, skew=-3.0, kurt=10.0)
    assert result["status"] == "computable"
    assert result["probability"] == pytest.approx(
        0.8996723484978978, abs=5e-13
    )


def test_dsr_single_trial_reduces_exactly_to_psr_zero_benchmark() -> None:
    dsr = deflated_sharpe_ratio(
        observed_sharpe_periodic=0.1,
        sample_count=252,
        skewness=0.0,
        pearson_kurtosis=3.0,
        trial_sharpe_std_periodic=None,
        independent_trial_count=1,
    )
    psr = probabilistic_sharpe_ratio(
        observed_sharpe_periodic=0.1,
        benchmark_sharpe_periodic=0.0,
        sample_count=252,
        skewness=0.0,
        pearson_kurtosis=3.0,
    )
    assert dsr["status"] == "computable"
    assert dsr["probability"] == psr["probability"]
    assert dsr["expected_maximum_sharpe_periodic"] == 0.0


def _equity_curve() -> list[tuple[str, float]]:
    return [
        ("2026-01-02", 100_000.0),
        ("2026-01-05", 101_125.25),
        ("2026-01-06", 100_810.75),
        ("2026-01-07", 102_430.5),
        ("2026-01-08", 101_990.125),
        ("2026-01-09", 103_225.875),
    ]


def test_backtest_builder_persists_full_precision_returns_hash_moments_and_psr() -> None:
    result = build_backtest_sharpe_inference(_equity_curve())
    repeated = build_backtest_sharpe_inference(_equity_curve())

    expected_returns = [
        current / previous - 1.0
        for previous, current in zip(
            [point[1] for point in _equity_curve()],
            [point[1] for point in _equity_curve()][1:],
        )
    ]
    expected_periodic_sharpe = statistics.fmean(expected_returns) / statistics.stdev(
        expected_returns
    )

    assert result["status"] == "computable"
    assert result["sample_count"] == 5
    assert [row["date"] for row in result["return_series"]] == [
        "2026-01-05",
        "2026-01-06",
        "2026-01-07",
        "2026-01-08",
        "2026-01-09",
    ]
    assert [row["return"] for row in result["return_series"]] == expected_returns
    assert result["periodic_sharpe"] == expected_periodic_sharpe
    assert result["annualized_sharpe"] == (
        expected_periodic_sharpe * math.sqrt(252)
    )
    assert result["return_series_sha256"] == repeated["return_series_sha256"]
    assert len(result["return_series_sha256"]) == 64
    assert result["moments"]["pearson_kurtosis"] >= 1.0
    assert result["psr"]["status"] == "computable"
    assert result["psr"]["benchmark_sharpe_periodic"] == 0.0
    assert result["dsr"]["status"] == "not_computable"
    assert result["dsr"]["reason_codes"] == [
        "complete_trial_panel_required",
        "trial_sharpe_dispersion_required",
        "effective_independent_trial_count_required",
    ]


def test_backtest_builder_hash_changes_with_return_evidence() -> None:
    original = build_backtest_sharpe_inference(_equity_curve())
    changed_curve = _equity_curve()
    changed_curve[-1] = (changed_curve[-1][0], changed_curve[-1][1] + 0.001)
    changed = build_backtest_sharpe_inference(changed_curve)
    assert original["return_series_sha256"] != changed["return_series_sha256"]


def test_backtest_builder_does_not_invent_sharpe_for_flat_equity() -> None:
    result = build_backtest_sharpe_inference(
        [
            ("2026-01-02", 100.0),
            ("2026-01-05", 100.0),
            ("2026-01-06", 100.0),
        ]
    )
    assert result["status"] == "not_computable"
    assert result["reason_codes"] == ["zero_or_invalid_return_variance"]
    assert result["psr"]["status"] == "not_computable"
    assert result["dsr"]["status"] == "not_computable"
    assert "probability" not in result["dsr"]


def _context() -> dict:
    return {
        "selection_scope": "core-policy-promotion-2026q1",
        "window": {"start": "2026-01-01", "end": "2026-01-07"},
        "frequency": "daily",
        "return_basis": "strategy_equity_return",
        "risk_free_assumption": "zero",
        "protocol": "canonical-backtest-v7",
        "data": "ohlcv-snapshot-sha256:abc",
        "cost": {"slippage_bps": 5, "commission_model": "v2"},
    }


def _return_rows(values: list[float], *, start_day: int = 2) -> list[dict]:
    return [
        {"date": f"2026-01-{day:02d}", "return": value}
        for day, value in enumerate(values, start=start_day)
    ]


def _trial(config_id: str, values: list[float], **overrides) -> dict:
    return_series = _return_rows(values)
    row = {
        "config_id": config_id,
        "config": {"variant": config_id},
        "attempted": True,
        "return_series": return_series,
        "return_series_sha256": hashlib.sha256(
            json.dumps(
                {"schema": "dated_periodic_return_series_v1", "rows": return_series},
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "return_series_source": f"data/backtests/{config_id}.json#sharpe_inference",
        **_context(),
    }
    row.update(overrides)
    return row


def _complete_panel() -> list[dict]:
    return [
        _trial("a", [0.010, -0.004, 0.006, -0.002, 0.008, 0.001]),
        _trial("b", [-0.003, 0.009, -0.001, 0.007, -0.004, 0.005]),
        _trial("c", [0.006, -0.002, 0.009, -0.005, 0.004, 0.003]),
    ]


def _expected_dates(panel: list[dict]) -> list[str]:
    return [row["date"] for row in panel[0]["return_series"]]


def test_complete_panel_computes_effective_n_trial_std_and_dsr() -> None:
    panel = _complete_panel()
    result = evaluate_deflated_sharpe_trial_panel(
        panel,
        selected_config_id="a",
        expected_attempt_count=3,
        selection_pool_complete=True,
        expected_return_dates=_expected_dates(panel),
    )

    expected_sharpes = []
    for trial in panel:
        returns = [row["return"] for row in trial["return_series"]]
        expected_sharpes.append(statistics.fmean(returns) / statistics.stdev(returns))

    assert result["status"] == "computable"
    assert result["raw_trial_count"] == 3
    assert result["sample_count"] == 6
    expected_effective_count = (
        result["average_pairwise_correlation"]
        + (1.0 - result["average_pairwise_correlation"]) * 3
    )
    assert result["effective_independent_trial_count"] == pytest.approx(
        expected_effective_count
    )
    assert 1.0 <= result["effective_independent_trial_count"] <= 4.0
    assert result["trial_sharpe_sample_std_periodic"] == pytest.approx(
        statistics.stdev(expected_sharpes)
    )
    assert result["trial_sharpe_dispersion_ddof"] == 1
    assert result["dsr"]["status"] == "computable"
    assert 0.0 <= result["dsr"]["probability"] <= 1.0
    assert result["panel_sha256"] == evaluate_deflated_sharpe_trial_panel(
        panel,
        selected_config_id="a",
        expected_attempt_count=3,
        selection_pool_complete=True,
        expected_return_dates=_expected_dates(panel),
    )["panel_sha256"]


def test_negative_average_pairwise_correlation_retains_paper_effective_n_penalty() -> None:
    panel = [
        _trial("long", [-0.01, 0.002, 0.015]),
        _trial("inverse", [0.01, -0.002, -0.015]),
    ]
    result = evaluate_deflated_sharpe_trial_panel(
        panel,
        selected_config_id="long",
        expected_attempt_count=2,
        selection_pool_complete=True,
        expected_return_dates=_expected_dates(panel),
    )
    assert result["status"] == "computable"
    assert result["average_pairwise_correlation"] == pytest.approx(-1.0)
    assert result["average_pairwise_correlation_for_effective_count"] == -1.0
    assert result["effective_independent_trial_count"] == 3.0
    assert "negative_average_pairwise_correlation_increases_effective_trial_count" in result[
        "warnings"
    ]


def test_positive_average_correlation_uses_paper_effective_n_interpolation() -> None:
    panel = [
        _trial("a", [0.010, -0.010, 0.020, -0.020, 0.015, -0.005]),
        _trial("b", [0.008, -0.015, 0.012, 0.005, -0.010, 0.020]),
        _trial("c", [-0.005, 0.010, 0.018, -0.012, 0.020, -0.002]),
    ]
    result = evaluate_deflated_sharpe_trial_panel(
        panel,
        selected_config_id="a",
        expected_attempt_count=3,
        selection_pool_complete=True,
        expected_return_dates=_expected_dates(panel),
    )
    assert result["status"] == "computable"
    rho = result["average_pairwise_correlation"]
    assert rho > 0.0
    assert result["average_pairwise_correlation_for_effective_count"] == rho
    assert result["effective_independent_trial_count"] == pytest.approx(
        rho + (1.0 - rho) * 3
    )
    assert "negative_average_pairwise_correlation_increases_effective_trial_count" not in result[
        "warnings"
    ]


@pytest.mark.parametrize(
    ("mutator", "reason"),
    [
        (
            lambda panel: panel[1].update(frequency="weekly"),
            "context_mismatch_frequency",
        ),
        (
            lambda panel: panel[1].update(return_basis="benchmark_excess_return"),
            "context_mismatch_return_basis",
        ),
        (
            lambda panel: panel[1].update(risk_free_assumption="daily_tbill"),
            "context_mismatch_risk_free_assumption",
        ),
        (
            lambda panel: panel[1].update(window={}),
            "trial_1_missing_context_window",
        ),
        (
            lambda panel: panel[1].update(return_series_source=""),
            "trial_1_missing_return_series_source",
        ),
        (
            lambda panel: panel[1].update(return_series_sha256="0" * 64),
            "trial_1_return_series_hash_mismatch",
        ),
        (
            lambda panel: panel[1].update(config=copy.deepcopy(panel[0]["config"])),
            "duplicate_config_payload",
        ),
        (
            lambda panel: panel[1].update(attempted=False),
            "trial_1_not_marked_attempted",
        ),
        (
            lambda panel: panel[1]["return_series"].__setitem__(
                0, {"date": "2026-01-01", "return": 0.01}
            ),
            "trial_return_dates_not_exactly_aligned",
        ),
    ],
)
def test_incomplete_or_incomparable_panel_fails_closed(mutator, reason: str) -> None:
    panel = _complete_panel()
    mutator(panel)
    result = evaluate_deflated_sharpe_trial_panel(
        panel,
        selected_config_id="a",
        expected_attempt_count=3,
        selection_pool_complete=True,
        expected_return_dates=_expected_dates(panel),
    )
    assert result["status"] == "not_computable"
    assert reason in result["reason_codes"]
    assert result["dsr"]["status"] == "not_computable"
    assert "probability" not in result["dsr"]


def test_panel_requires_declared_complete_attempt_count() -> None:
    result = evaluate_deflated_sharpe_trial_panel(
        _complete_panel(),
        selected_config_id="a",
        expected_attempt_count=None,
        selection_pool_complete=True,
        expected_return_dates=_expected_dates(_complete_panel()),
    )
    assert result["status"] == "not_computable"
    assert "missing_or_invalid_expected_attempt_count" in result["reason_codes"]


def test_panel_requires_explicit_complete_pool_attestation() -> None:
    result = evaluate_deflated_sharpe_trial_panel(
        _complete_panel(),
        selected_config_id="a",
        expected_attempt_count=3,
        selection_pool_complete=None,
        expected_return_dates=_expected_dates(_complete_panel()),
    )
    assert result["status"] == "not_computable"
    assert "selection_pool_not_declared_complete" in result["reason_codes"]


def test_panel_rejects_common_date_deletion_against_expected_vector() -> None:
    panel = _complete_panel()
    expected_dates = _expected_dates(panel)
    for trial in panel:
        trial["return_series"].pop()
        trial["return_series_sha256"] = hashlib.sha256(
            json.dumps(
                {
                    "schema": "dated_periodic_return_series_v1",
                    "rows": trial["return_series"],
                },
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    result = evaluate_deflated_sharpe_trial_panel(
        panel,
        selected_config_id="a",
        expected_attempt_count=3,
        selection_pool_complete=True,
        expected_return_dates=expected_dates,
    )
    assert result["status"] == "not_computable"
    assert "trial_return_dates_do_not_match_expected_vector" in result["reason_codes"]


def test_panel_attempt_count_mismatch_fails_closed() -> None:
    result = evaluate_deflated_sharpe_trial_panel(
        _complete_panel(),
        selected_config_id="a",
        expected_attempt_count=4,
        selection_pool_complete=True,
        expected_return_dates=_expected_dates(_complete_panel()),
    )
    assert result["status"] == "not_computable"
    assert "trial_panel_attempt_count_mismatch" in result["reason_codes"]


def test_panel_rejects_t_less_than_m() -> None:
    panel = [
        _trial(f"config-{index}", [0.01 + index / 1000, -0.004, 0.002])
        for index in range(4)
    ]
    result = evaluate_deflated_sharpe_trial_panel(
        panel,
        selected_config_id="config-0",
        expected_attempt_count=4,
        selection_pool_complete=True,
        expected_return_dates=_expected_dates(panel),
    )
    assert result["status"] == "not_computable"
    assert "return_sample_count_below_trial_count" in result["reason_codes"]
