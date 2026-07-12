"""Selection-aware Sharpe inference using the Bailey--Lopez de Prado formulas.

This module deliberately separates three different evidence levels:

* :func:`probabilistic_sharpe_ratio` evaluates one periodic, non-annualized
  Sharpe estimate against an explicitly supplied periodic benchmark.
* :func:`deflated_sharpe_ratio` additionally requires an explicit dispersion
  of comparable trial Sharpes and an independent-trial count.
* :func:`evaluate_deflated_sharpe_trial_panel` derives those DSR inputs only
  from a declared, complete and homogeneous trial panel.

Missing selection evidence is represented as ``status == "not_computable"``.
The module never substitutes a trial count, a Sharpe standard error, or a
rounded historical Sharpe for missing evidence.

All formula inputs are Sharpe ratios at the observation frequency.  Annualized
values are display fields only and never enter the PSR/DSR denominator.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any


SCHEMA_VERSION = 1
EULER_MASCHERONI = 0.5772156649015329
_NORMAL = statistics.NormalDist()
_SMALL_SAMPLE_WARNING_THRESHOLD = 30
_SMALL_TRIAL_APPROXIMATION_THRESHOLD = 50
_PANEL_CONTEXT_KEYS = (
    "selection_scope",
    "window",
    "frequency",
    "return_basis",
    "risk_free_assumption",
    "protocol",
    "data",
    "cost",
)


def _ordered_unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))


def _not_computable(reason_codes: Sequence[str], **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "not_computable",
        "reason_codes": _ordered_unique(reason_codes),
    }
    result.update(extra)
    return result


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _finite_float(value: Any) -> float | None:
    if not _is_number(value):
        return None
    converted = float(value)
    return converted if math.isfinite(converted) else None


def _positive_integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        converted = int(value)
        return converted if converted > 0 else None
    return None


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_date(value: Any) -> tuple[str, date] | None:
    if isinstance(value, datetime):
        parsed = value.date()
        return parsed.isoformat(), parsed
    if isinstance(value, date):
        return value.isoformat(), value
    if not isinstance(value, str):
        return None
    label = value.strip()
    if not label:
        return None
    try:
        parsed = date.fromisoformat(label)
    except ValueError:
        return None
    return parsed.isoformat(), parsed


def expected_maximum_sharpe(
    *,
    trial_sharpe_std_periodic: float | None,
    independent_trial_count: float,
) -> dict[str, Any]:
    """Approximate the expected maximum periodic Sharpe under a zero-skill null.

    This is Eq. (2) in Bailey and Lopez de Prado (2014).  The approximation is
    asymptotic in the number of independent trials.  ``N == 1`` is handled
    explicitly because the inverse-normal expression is singular even though
    the expected maximum under the zero-mean null is exactly zero.
    """

    count = _finite_float(independent_trial_count)
    if count is None:
        return _not_computable(["invalid_independent_trial_count"])
    if count < 1.0:
        return _not_computable(["independent_trial_count_below_one"])

    if count == 1.0:
        return {
            "status": "computable",
            "independent_trial_count": 1.0,
            "trial_sharpe_std_periodic": (
                _finite_float(trial_sharpe_std_periodic)
                if trial_sharpe_std_periodic is not None
                else None
            ),
            "extreme_value_z": 0.0,
            "expected_maximum_sharpe_periodic": 0.0,
            "method": "single_trial_zero_skill_null",
            "warnings": [],
        }

    std = _finite_float(trial_sharpe_std_periodic)
    if std is None:
        return _not_computable(["missing_or_invalid_trial_sharpe_std"])
    if std < 0.0:
        return _not_computable(["negative_trial_sharpe_std"])

    first_probability = 1.0 - (1.0 / count)
    second_probability = 1.0 - (1.0 / (count * math.e))
    if not (
        0.0 < first_probability < 1.0
        and 0.0 < second_probability < 1.0
    ):
        return _not_computable(
            ["independent_trial_count_out_of_numeric_range"]
        )

    try:
        extreme_value_z = (
            (1.0 - EULER_MASCHERONI)
            * _NORMAL.inv_cdf(first_probability)
            + EULER_MASCHERONI
            * _NORMAL.inv_cdf(second_probability)
        )
    except statistics.StatisticsError:
        return _not_computable(["inverse_normal_not_computable"])

    expected_maximum = std * extreme_value_z
    if not (math.isfinite(extreme_value_z) and math.isfinite(expected_maximum)):
        return _not_computable(["expected_maximum_not_finite"])
    # Eq. (2) is a large-N approximation.  When a continuous effective-N
    # estimate lies only fractionally above one, the approximation can become
    # negative even though the maximum of one or more zero-mean trials cannot
    # have a negative expectation.  Treat that domain as unavailable rather
    # than letting a purported "deflation" raise PSR above its one-trial value.
    if expected_maximum < 0.0:
        return _not_computable(
            ["expected_maximum_approximation_negative"],
            independent_trial_count=count,
            trial_sharpe_std_periodic=std,
            extreme_value_z=extreme_value_z,
        )

    warnings: list[str] = []
    if count < _SMALL_TRIAL_APPROXIMATION_THRESHOLD:
        warnings.append("small_independent_trial_count_extreme_value_approximation")

    return {
        "status": "computable",
        "independent_trial_count": count,
        "trial_sharpe_std_periodic": std,
        "extreme_value_z": extreme_value_z,
        "expected_maximum_sharpe_periodic": expected_maximum,
        "method": "bailey_lopez_de_prado_expected_maximum_v1",
        "warnings": warnings,
    }


def probabilistic_sharpe_ratio(
    *,
    observed_sharpe_periodic: float,
    benchmark_sharpe_periodic: float,
    sample_count: int,
    skewness: float,
    pearson_kurtosis: float,
) -> dict[str, Any]:
    """Compute the Bailey--Lopez de Prado Probabilistic Sharpe Ratio.

    ``pearson_kurtosis`` must use the Pearson convention (Normal == 3), not
    excess/Fisher kurtosis (Normal == 0).  The higher-moment denominator uses
    the observed Sharpe estimate, not the benchmark Sharpe.
    """

    observed = _finite_float(observed_sharpe_periodic)
    benchmark = _finite_float(benchmark_sharpe_periodic)
    skew = _finite_float(skewness)
    kurtosis = _finite_float(pearson_kurtosis)
    count = _positive_integer(sample_count)

    reasons: list[str] = []
    if observed is None:
        reasons.append("invalid_observed_sharpe")
    if benchmark is None:
        reasons.append("invalid_benchmark_sharpe")
    if skew is None:
        reasons.append("invalid_skewness")
    if kurtosis is None:
        reasons.append("invalid_pearson_kurtosis")
    elif kurtosis < 1.0:
        reasons.append("pearson_kurtosis_below_theoretical_minimum")
    if count is None:
        reasons.append("invalid_sample_count")
    elif count < 2:
        reasons.append("sample_count_below_two")
    if reasons:
        return _not_computable(reasons)

    assert observed is not None
    assert benchmark is not None
    assert skew is not None
    assert kurtosis is not None
    assert count is not None

    variance_numerator = (
        1.0
        - skew * observed
        + ((kurtosis - 1.0) / 4.0) * observed * observed
    )
    if not math.isfinite(variance_numerator):
        return _not_computable(["sharpe_asymptotic_variance_not_finite"])
    if variance_numerator <= 0.0:
        return _not_computable(["sharpe_asymptotic_variance_not_positive"])

    standard_error = math.sqrt(variance_numerator / (count - 1))
    if not math.isfinite(standard_error) or standard_error <= 0.0:
        return _not_computable(["sharpe_standard_error_not_positive"])

    z_score = (observed - benchmark) / standard_error
    if not math.isfinite(z_score):
        return _not_computable(["psr_z_score_not_finite"])
    probability = _NORMAL.cdf(z_score)
    if not math.isfinite(probability):
        return _not_computable(["psr_probability_not_finite"])

    warnings: list[str] = []
    if count < _SMALL_SAMPLE_WARNING_THRESHOLD:
        warnings.append("small_return_sample_asymptotic_inference")

    return {
        "status": "computable",
        "probability": probability,
        "z_score": z_score,
        "observed_sharpe_periodic": observed,
        "benchmark_sharpe_periodic": benchmark,
        "sample_count": count,
        "skewness": skew,
        "pearson_kurtosis": kurtosis,
        "asymptotic_variance_numerator": variance_numerator,
        "standard_error_periodic": standard_error,
        "formula": "bailey_lopez_de_prado_psr_v1",
        "warnings": warnings,
    }


def deflated_sharpe_ratio(
    *,
    observed_sharpe_periodic: float,
    sample_count: int,
    skewness: float,
    pearson_kurtosis: float,
    trial_sharpe_std_periodic: float | None,
    independent_trial_count: float,
) -> dict[str, Any]:
    """Compute DSR from an explicit periodic trial dispersion and trial count."""

    expected = expected_maximum_sharpe(
        trial_sharpe_std_periodic=trial_sharpe_std_periodic,
        independent_trial_count=independent_trial_count,
    )
    if expected["status"] != "computable":
        return _not_computable(
            expected.get("reason_codes", ["expected_maximum_not_computable"]),
            expected_maximum=expected,
        )

    psr = probabilistic_sharpe_ratio(
        observed_sharpe_periodic=observed_sharpe_periodic,
        benchmark_sharpe_periodic=expected[
            "expected_maximum_sharpe_periodic"
        ],
        sample_count=sample_count,
        skewness=skewness,
        pearson_kurtosis=pearson_kurtosis,
    )
    if psr["status"] != "computable":
        return _not_computable(
            psr.get("reason_codes", ["psr_not_computable"]),
            expected_maximum=expected,
            psr=psr,
        )

    warnings = _ordered_unique(
        list(expected.get("warnings") or []) + list(psr.get("warnings") or [])
    )
    return {
        "status": "computable",
        "probability": psr["probability"],
        "z_score": psr["z_score"],
        "observed_sharpe_periodic": psr["observed_sharpe_periodic"],
        "sample_count": psr["sample_count"],
        "skewness": psr["skewness"],
        "pearson_kurtosis": psr["pearson_kurtosis"],
        "trial_sharpe_std_periodic": expected[
            "trial_sharpe_std_periodic"
        ],
        "independent_trial_count": expected["independent_trial_count"],
        "expected_maximum_sharpe_periodic": expected[
            "expected_maximum_sharpe_periodic"
        ],
        "extreme_value_z": expected["extreme_value_z"],
        "standard_error_periodic": psr["standard_error_periodic"],
        "asymptotic_variance_numerator": psr[
            "asymptotic_variance_numerator"
        ],
        "formula": "bailey_lopez_de_prado_dsr_v1",
        "warnings": warnings,
    }


def _statistics_from_returns(values: Sequence[float]) -> dict[str, Any]:
    reasons: list[str] = []
    if len(values) < 2:
        return _not_computable(["return_sample_count_below_two"])
    converted: list[float] = []
    for value in values:
        item = _finite_float(value)
        if item is None:
            reasons.append("non_finite_return")
        else:
            converted.append(item)
    if reasons:
        return _not_computable(reasons)

    mean_return = math.fsum(converted) / len(converted)
    try:
        sample_std = statistics.stdev(converted)
    except statistics.StatisticsError:
        return _not_computable(["return_sample_standard_deviation_unavailable"])
    if not math.isfinite(sample_std) or sample_std <= 0.0:
        return _not_computable(["zero_or_invalid_return_variance"])

    deviations = [value - mean_return for value in converted]
    count = len(converted)
    central_moment_2 = math.fsum(value**2 for value in deviations) / count
    central_moment_3 = math.fsum(value**3 for value in deviations) / count
    central_moment_4 = math.fsum(value**4 for value in deviations) / count
    if not math.isfinite(central_moment_2) or central_moment_2 <= 0.0:
        return _not_computable(["central_second_moment_not_positive"])

    skewness = central_moment_3 / (central_moment_2 ** 1.5)
    pearson_kurtosis = central_moment_4 / (central_moment_2**2)
    periodic_sharpe = mean_return / sample_std
    if not all(
        math.isfinite(value)
        for value in (skewness, pearson_kurtosis, periodic_sharpe)
    ):
        return _not_computable(["return_moments_not_finite"])
    if pearson_kurtosis < 1.0 - 1e-12:
        return _not_computable(["estimated_pearson_kurtosis_inconsistent"])
    # Avoid rejecting a theoretical boundary because of sub-ulp roundoff.
    pearson_kurtosis = max(1.0, pearson_kurtosis)

    return {
        "status": "computable",
        "sample_count": count,
        "mean_periodic_return": mean_return,
        "sample_standard_deviation_periodic": sample_std,
        "sample_standard_deviation_ddof": 1,
        "central_moment_2": central_moment_2,
        "central_moment_3": central_moment_3,
        "central_moment_4": central_moment_4,
        "moment_estimator": "empirical_central_moments_divisor_n",
        "skewness": skewness,
        "pearson_kurtosis": pearson_kurtosis,
        "periodic_sharpe": periodic_sharpe,
    }


def _parse_equity_curve(
    equity_curve: Any,
) -> tuple[list[dict[str, Any]] | None, list[str]]:
    if not isinstance(equity_curve, Sequence) or isinstance(
        equity_curve, (str, bytes, bytearray)
    ):
        return None, ["equity_curve_not_a_sequence"]
    if len(equity_curve) < 3:
        return None, ["equity_curve_needs_at_least_three_points"]

    normalized: list[dict[str, Any]] = []
    reasons: list[str] = []
    previous_date: date | None = None
    for index, point in enumerate(equity_curve):
        if isinstance(point, Mapping):
            raw_date = point.get("date")
            raw_equity = point.get("equity")
        elif isinstance(point, Sequence) and not isinstance(
            point, (str, bytes, bytearray)
        ) and len(point) == 2:
            raw_date, raw_equity = point
        else:
            reasons.append(f"invalid_equity_point_{index}")
            continue

        normalized_date = _normalize_date(raw_date)
        if normalized_date is None:
            reasons.append(f"invalid_equity_date_{index}")
            continue
        date_label, parsed_date = normalized_date
        if previous_date is not None and parsed_date <= previous_date:
            reasons.append("equity_dates_not_strictly_increasing")
        previous_date = parsed_date

        equity = _finite_float(raw_equity)
        if equity is None:
            reasons.append(f"invalid_equity_value_{index}")
            continue
        if equity <= 0.0:
            reasons.append(f"non_positive_equity_value_{index}")
            continue
        normalized.append({"date": date_label, "equity": equity})

    if reasons:
        return None, _ordered_unique(reasons)
    return normalized, []


def _parse_return_series(
    return_series: Any,
) -> tuple[list[dict[str, Any]] | None, list[str]]:
    if not isinstance(return_series, Sequence) or isinstance(
        return_series, (str, bytes, bytearray)
    ):
        return None, ["return_series_not_a_sequence"]
    if len(return_series) < 2:
        return None, ["return_series_needs_at_least_two_points"]

    normalized: list[dict[str, Any]] = []
    reasons: list[str] = []
    previous_date: date | None = None
    for index, point in enumerate(return_series):
        if isinstance(point, Mapping):
            raw_date = point.get("date")
            raw_return = point.get("return")
        elif isinstance(point, Sequence) and not isinstance(
            point, (str, bytes, bytearray)
        ) and len(point) == 2:
            raw_date, raw_return = point
        else:
            reasons.append(f"invalid_return_point_{index}")
            continue

        normalized_date = _normalize_date(raw_date)
        if normalized_date is None:
            reasons.append(f"invalid_return_date_{index}")
            continue
        date_label, parsed_date = normalized_date
        if previous_date is not None and parsed_date <= previous_date:
            reasons.append("return_dates_not_strictly_increasing")
        previous_date = parsed_date

        value = _finite_float(raw_return)
        if value is None:
            reasons.append(f"invalid_return_value_{index}")
            continue
        normalized.append({"date": date_label, "return": value})

    if reasons:
        return None, _ordered_unique(reasons)
    return normalized, []


def _parse_expected_return_dates(
    expected_return_dates: Any,
) -> tuple[list[str] | None, list[str]]:
    if not isinstance(expected_return_dates, Sequence) or isinstance(
        expected_return_dates, (str, bytes, bytearray)
    ):
        return None, ["expected_return_dates_not_a_sequence"]
    if len(expected_return_dates) < 2:
        return None, ["expected_return_dates_needs_at_least_two_dates"]

    labels: list[str] = []
    reasons: list[str] = []
    previous_date: date | None = None
    for index, raw_date in enumerate(expected_return_dates):
        normalized = _normalize_date(raw_date)
        if normalized is None:
            reasons.append(f"invalid_expected_return_date_{index}")
            continue
        label, parsed = normalized
        if previous_date is not None and parsed <= previous_date:
            reasons.append("expected_return_dates_not_strictly_increasing")
        previous_date = parsed
        labels.append(label)
    if reasons:
        return None, _ordered_unique(reasons)
    return labels, []


def build_backtest_sharpe_inference(
    equity_curve: Any,
    periods_per_year: int = 252,
    return_basis: str = "strategy_equity_return",
    risk_free_assumption: str = "zero",
) -> dict[str, Any]:
    """Build auditable PSR evidence from a dated backtest equity curve.

    The result intentionally leaves DSR uncomputed.  DSR needs the complete
    selection panel accepted by :func:`evaluate_deflated_sharpe_trial_panel`;
    one strategy's equity curve cannot supply trial dispersion or an effective
    independent-trial count.
    """

    periods = _positive_integer(periods_per_year)
    metadata_reasons: list[str] = []
    if periods is None:
        metadata_reasons.append("invalid_periods_per_year")
    if not isinstance(return_basis, str) or not return_basis.strip():
        metadata_reasons.append("missing_return_basis")
    if not isinstance(risk_free_assumption, str) or not risk_free_assumption.strip():
        metadata_reasons.append("missing_risk_free_assumption")

    normalized_curve, curve_reasons = _parse_equity_curve(equity_curve)
    reasons = metadata_reasons + curve_reasons
    if reasons:
        unavailable = _not_computable(reasons)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "not_computable",
            "reason_codes": _ordered_unique(reasons),
            "psr": unavailable,
            "dsr": _not_computable(
                [
                    "complete_trial_panel_required",
                    "trial_sharpe_dispersion_required",
                    "effective_independent_trial_count_required",
                ]
                + reasons
            ),
        }

    assert normalized_curve is not None
    assert periods is not None

    return_series: list[dict[str, Any]] = []
    for previous, current in zip(normalized_curve, normalized_curve[1:]):
        periodic_return = current["equity"] / previous["equity"] - 1.0
        if not math.isfinite(periodic_return):
            unavailable = _not_computable(["derived_return_not_finite"])
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "not_computable",
                "reason_codes": unavailable["reason_codes"],
                "psr": unavailable,
                "dsr": _not_computable(
                    [
                        "complete_trial_panel_required",
                        "trial_sharpe_dispersion_required",
                        "effective_independent_trial_count_required",
                        "derived_return_not_finite",
                    ]
                ),
            }
        return_series.append(
            {"date": current["date"], "return": periodic_return}
        )

    stats = _statistics_from_returns(
        [point["return"] for point in return_series]
    )
    if stats["status"] != "computable":
        reasons = stats.get("reason_codes", ["return_statistics_not_computable"])
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "not_computable",
            "reason_codes": reasons,
            "return_basis": return_basis.strip(),
            "risk_free_assumption": risk_free_assumption.strip(),
            "periods_per_year": periods,
            "return_series": return_series,
            "return_series_sha256": _stable_hash(
                {"schema": "dated_periodic_return_series_v1", "rows": return_series}
            ),
            "psr": _not_computable(reasons),
            "dsr": _not_computable(
                [
                    "complete_trial_panel_required",
                    "trial_sharpe_dispersion_required",
                    "effective_independent_trial_count_required",
                ]
                + list(reasons)
            ),
        }

    psr = probabilistic_sharpe_ratio(
        observed_sharpe_periodic=stats["periodic_sharpe"],
        benchmark_sharpe_periodic=0.0,
        sample_count=stats["sample_count"],
        skewness=stats["skewness"],
        pearson_kurtosis=stats["pearson_kurtosis"],
    )
    if psr["status"] != "computable":
        reasons = psr.get("reason_codes", ["psr_not_computable"])
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "not_computable",
            "reason_codes": reasons,
            "return_basis": return_basis.strip(),
            "risk_free_assumption": risk_free_assumption.strip(),
            "periods_per_year": periods,
            "return_series": return_series,
            "return_series_sha256": _stable_hash(
                {"schema": "dated_periodic_return_series_v1", "rows": return_series}
            ),
            "moments": stats,
            "psr": psr,
            "dsr": _not_computable(
                [
                    "complete_trial_panel_required",
                    "trial_sharpe_dispersion_required",
                    "effective_independent_trial_count_required",
                ]
                + list(reasons)
            ),
        }

    annualized_sharpe = stats["periodic_sharpe"] * math.sqrt(periods)
    return_hash = _stable_hash(
        {"schema": "dated_periodic_return_series_v1", "rows": return_series}
    )
    dsr = _not_computable(
        [
            "complete_trial_panel_required",
            "trial_sharpe_dispersion_required",
            "effective_independent_trial_count_required",
        ]
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "computable",
        "return_basis": return_basis.strip(),
        "risk_free_assumption": risk_free_assumption.strip(),
        "periods_per_year": periods,
        "formula_periodicity": "periodic_non_annualized",
        "stationarity_assumption": "stationary_and_ergodic",
        "serial_conditionality": "unadjusted",
        "sample_count": stats["sample_count"],
        "periodic_sharpe": stats["periodic_sharpe"],
        "annualized_sharpe": annualized_sharpe,
        "return_series": return_series,
        "return_series_sha256": return_hash,
        "return_series_hash_method": "sha256_canonical_json_v1",
        "moments": {
            key: value
            for key, value in stats.items()
            if key not in {"status", "periodic_sharpe"}
        },
        "psr": psr,
        "dsr": dsr,
        "warnings": list(psr.get("warnings") or []),
    }


def _context_is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return bool(value)
    return True


def _pairwise_correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = math.fsum(left) / len(left)
    right_mean = math.fsum(right) / len(right)
    left_deviation = [value - left_mean for value in left]
    right_deviation = [value - right_mean for value in right]
    numerator = math.fsum(
        a * b for a, b in zip(left_deviation, right_deviation)
    )
    left_sum_squares = math.fsum(value * value for value in left_deviation)
    right_sum_squares = math.fsum(value * value for value in right_deviation)
    denominator = math.sqrt(left_sum_squares * right_sum_squares)
    if not math.isfinite(denominator) or denominator <= 0.0:
        return None
    correlation = numerator / denominator
    if not math.isfinite(correlation):
        return None
    if correlation > 1.0:
        if correlation <= 1.0 + 1e-12:
            return 1.0
        return None
    if correlation < -1.0:
        if correlation >= -1.0 - 1e-12:
            return -1.0
        return None
    return correlation


def evaluate_deflated_sharpe_trial_panel(
    trials: Any,
    *,
    selected_config_id: str,
    expected_attempt_count: int | None,
    selection_pool_complete: bool | None = None,
    expected_return_dates: Any = None,
    periods_per_year: int = 252,
) -> dict[str, Any]:
    """Evaluate DSR from a complete, comparable trial panel.

    Every trial mapping must contain:

    ``config_id``
        A unique identifier.
    ``config``
        The complete tested configuration; duplicate configurations are
        rejected even when their identifiers differ.
    ``attempted``
        Exactly ``True``.  Together with ``expected_attempt_count`` this makes
        omission of attempted losers a machine-visible failure.
    ``selection_scope``, ``window``, ``frequency``, ``return_basis``,
    ``risk_free_assumption``, ``protocol``, ``data``, ``cost``
        Non-empty, JSON-serializable context values identical across trials.
    ``return_series``
        Strictly increasing ``[{"date": YYYY-MM-DD, "return": float}, ...]``
        (two-item rows are also accepted).  Date vectors must match exactly.

    ``selection_pool_complete`` must separately be passed as exactly ``True``;
    ``expected_attempt_count`` must then match the number of rows.  This is an
    explicit auditable attestation, not an inferred historical trial count.
    ``expected_return_dates`` must be the authoritative ordered date vector
    from the evaluation protocol, not one inferred from the submitted winner.
    Each row must also carry the persisted ``return_series_sha256`` and a
    non-empty ``return_series_source`` locator.

    The panel is rejected unless ``M >= 2`` and ``T >= M``.  Effective trial
    count follows the paper's average-correlation interpolation.  A negative
    average correlation can make the effective count exceed the raw count;
    that extra selection penalty is retained and disclosed with a warning.
    """

    reasons: list[str] = []
    if selection_pool_complete is not True:
        reasons.append("selection_pool_not_declared_complete")
    expected_dates, expected_date_reasons = _parse_expected_return_dates(
        expected_return_dates
    )
    reasons.extend(expected_date_reasons)
    periods = _positive_integer(periods_per_year)
    if periods is None:
        reasons.append("invalid_periods_per_year")

    expected_count = _positive_integer(expected_attempt_count)
    if expected_count is None:
        reasons.append("missing_or_invalid_expected_attempt_count")

    if not isinstance(selected_config_id, str) or not selected_config_id.strip():
        reasons.append("missing_selected_config_id")
        selected_id = ""
    else:
        selected_id = selected_config_id.strip()

    if not isinstance(trials, Sequence) or isinstance(
        trials, (str, bytes, bytearray)
    ):
        reasons.append("trial_panel_not_a_sequence")
        return {
            "schema_version": SCHEMA_VERSION,
            **_not_computable(reasons),
            "dsr": _not_computable(reasons),
        }

    trial_rows = list(trials)
    raw_trial_count = len(trial_rows)
    if raw_trial_count < 2:
        reasons.append("trial_panel_needs_at_least_two_trials")
    if expected_count is not None and raw_trial_count != expected_count:
        reasons.append("trial_panel_attempt_count_mismatch")

    normalized_trials: list[dict[str, Any]] = []
    config_ids: list[str] = []
    config_hashes: list[str] = []
    reference_context: dict[str, str] | None = None

    for index, raw_trial in enumerate(trial_rows):
        if not isinstance(raw_trial, Mapping):
            reasons.append(f"trial_{index}_not_a_mapping")
            continue

        if raw_trial.get("attempted") is not True:
            reasons.append(f"trial_{index}_not_marked_attempted")

        config_id_value = raw_trial.get("config_id")
        if not isinstance(config_id_value, str) or not config_id_value.strip():
            reasons.append(f"trial_{index}_missing_config_id")
            config_id = f"__invalid_{index}"
        else:
            config_id = config_id_value.strip()
            config_ids.append(config_id)

        if "config" not in raw_trial or not _context_is_present(raw_trial.get("config")):
            reasons.append(f"trial_{index}_missing_config")
            config_value: Any = None
            config_hash = f"__invalid_{index}"
        else:
            config_value = raw_trial.get("config")
            try:
                config_hash = _stable_hash(
                    {"schema": "trial_config_v1", "config": config_value}
                )
                config_hashes.append(config_hash)
            except (TypeError, ValueError):
                reasons.append(f"trial_{index}_config_not_canonical_json")
                config_hash = f"__invalid_{index}"

        context_canonical: dict[str, str] = {}
        context_values: dict[str, Any] = {}
        for key in _PANEL_CONTEXT_KEYS:
            value = raw_trial.get(key)
            if not _context_is_present(value):
                reasons.append(f"trial_{index}_missing_context_{key}")
                continue
            try:
                context_canonical[key] = _canonical_json(value)
                context_values[key] = value
            except (TypeError, ValueError):
                reasons.append(f"trial_{index}_context_{key}_not_canonical_json")

        if len(context_canonical) == len(_PANEL_CONTEXT_KEYS):
            if reference_context is None:
                reference_context = context_canonical
            else:
                for key in _PANEL_CONTEXT_KEYS:
                    if context_canonical.get(key) != reference_context.get(key):
                        reasons.append(f"context_mismatch_{key}")

        normalized_returns, return_reasons = _parse_return_series(
            raw_trial.get("return_series")
        )
        reasons.extend(f"trial_{index}_{reason}" for reason in return_reasons)
        return_series_source = raw_trial.get("return_series_source")
        if not isinstance(return_series_source, str) or not return_series_source.strip():
            reasons.append(f"trial_{index}_missing_return_series_source")
            return_series_source = None
        else:
            return_series_source = return_series_source.strip()
        claimed_return_hash = raw_trial.get("return_series_sha256")
        if not isinstance(claimed_return_hash, str) or not claimed_return_hash.strip():
            reasons.append(f"trial_{index}_missing_return_series_sha256")
            claimed_return_hash = None
        else:
            claimed_return_hash = claimed_return_hash.strip().lower()
        computed_return_hash = None
        if normalized_returns is not None:
            computed_return_hash = _stable_hash(
                {
                    "schema": "dated_periodic_return_series_v1",
                    "rows": normalized_returns,
                }
            )
            if claimed_return_hash != computed_return_hash:
                reasons.append(f"trial_{index}_return_series_hash_mismatch")
        normalized_trials.append(
            {
                "config_id": config_id,
                "config": config_value,
                "config_sha256": config_hash,
                "context": context_values,
                "return_series": normalized_returns,
                "return_series_source": return_series_source,
                "return_series_sha256": computed_return_hash,
            }
        )

    if len(config_ids) != len(set(config_ids)):
        reasons.append("duplicate_config_id")
    if len(config_hashes) != len(set(config_hashes)):
        reasons.append("duplicate_config_payload")
    if selected_id and config_ids.count(selected_id) != 1:
        reasons.append("selected_config_not_present_exactly_once")

    valid_series = [
        trial["return_series"]
        for trial in normalized_trials
        if trial["return_series"] is not None
    ]
    sample_count: int | None = None
    if valid_series:
        reference_dates = [row["date"] for row in valid_series[0]]
        sample_count = len(expected_dates) if expected_dates is not None else len(reference_dates)
        if expected_dates is not None and reference_dates != expected_dates:
            reasons.append("trial_return_dates_do_not_match_expected_vector")
        for series in valid_series[1:]:
            dates = [row["date"] for row in series]
            if dates != reference_dates:
                reasons.append("trial_return_dates_not_exactly_aligned")
            if expected_dates is not None and dates != expected_dates:
                reasons.append("trial_return_dates_do_not_match_expected_vector")
        if sample_count < raw_trial_count:
            reasons.append("return_sample_count_below_trial_count")
    elif raw_trial_count:
        reasons.append("no_valid_trial_return_series")

    if reasons:
        unavailable = _not_computable(_ordered_unique(reasons))
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "not_computable",
            "reason_codes": unavailable["reason_codes"],
            "raw_trial_count": raw_trial_count,
            "expected_attempt_count": expected_attempt_count,
            "selection_pool_complete": selection_pool_complete is True,
            "sample_count": sample_count,
            "selected_config_id": selected_id or None,
            "dsr": unavailable,
        }

    assert periods is not None
    assert expected_count is not None
    assert expected_dates is not None
    assert reference_context is not None
    assert sample_count is not None

    stats_by_id: dict[str, dict[str, Any]] = {}
    values_by_id: dict[str, list[float]] = {}
    normalized_by_id: dict[str, dict[str, Any]] = {}
    for trial in normalized_trials:
        assert trial["return_series"] is not None
        values = [row["return"] for row in trial["return_series"]]
        stats = _statistics_from_returns(values)
        if stats["status"] != "computable":
            panel_reasons = [
                f"trial_{trial['config_id']}_{reason}"
                for reason in stats.get(
                    "reason_codes", ["return_statistics_not_computable"]
                )
            ]
            unavailable = _not_computable(panel_reasons)
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "not_computable",
                "reason_codes": unavailable["reason_codes"],
                "raw_trial_count": raw_trial_count,
                "expected_attempt_count": expected_count,
                "selection_pool_complete": True,
                "sample_count": sample_count,
                "selected_config_id": selected_id,
                "dsr": unavailable,
            }
        stats_by_id[trial["config_id"]] = stats
        values_by_id[trial["config_id"]] = values
        normalized_by_id[trial["config_id"]] = trial

    correlations: list[float] = []
    correlation_rows: list[dict[str, Any]] = []
    for left_index, left_id in enumerate(config_ids):
        for right_id in config_ids[left_index + 1 :]:
            correlation = _pairwise_correlation(
                values_by_id[left_id], values_by_id[right_id]
            )
            if correlation is None:
                unavailable = _not_computable(
                    [f"pairwise_correlation_not_computable_{left_id}_{right_id}"]
                )
                return {
                    "schema_version": SCHEMA_VERSION,
                    "status": "not_computable",
                    "reason_codes": unavailable["reason_codes"],
                    "raw_trial_count": raw_trial_count,
                    "expected_attempt_count": expected_count,
                    "selection_pool_complete": True,
                    "sample_count": sample_count,
                    "selected_config_id": selected_id,
                    "dsr": unavailable,
                }
            correlations.append(correlation)
            correlation_rows.append(
                {
                    "left_config_id": left_id,
                    "right_config_id": right_id,
                    "correlation": correlation,
                }
            )

    average_correlation = math.fsum(correlations) / len(correlations)
    warnings: list[str] = []
    if average_correlation < 0.0:
        warnings.append(
            "negative_average_pairwise_correlation_increases_effective_trial_count"
        )
    correlation_for_count = average_correlation
    effective_count = (
        correlation_for_count
        + (1.0 - correlation_for_count) * raw_trial_count
    )
    if not math.isfinite(effective_count) or effective_count < 1.0:
        unavailable = _not_computable(["effective_trial_count_not_valid"])
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "not_computable",
            "reason_codes": unavailable["reason_codes"],
            "raw_trial_count": raw_trial_count,
            "expected_attempt_count": expected_count,
            "selection_pool_complete": True,
            "sample_count": sample_count,
            "selected_config_id": selected_id,
            "dsr": unavailable,
        }

    periodic_sharpes = [
        stats_by_id[config_id]["periodic_sharpe"] for config_id in config_ids
    ]
    trial_sharpe_std = statistics.stdev(periodic_sharpes)
    selected_stats = stats_by_id[selected_id]
    selected_trial = normalized_by_id[selected_id]

    dsr = deflated_sharpe_ratio(
        observed_sharpe_periodic=selected_stats["periodic_sharpe"],
        sample_count=sample_count,
        skewness=selected_stats["skewness"],
        pearson_kurtosis=selected_stats["pearson_kurtosis"],
        trial_sharpe_std_periodic=trial_sharpe_std,
        independent_trial_count=effective_count,
    )
    if dsr["status"] != "computable":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "not_computable",
            "reason_codes": dsr.get(
                "reason_codes", ["dsr_formula_not_computable"]
            ),
            "raw_trial_count": raw_trial_count,
            "expected_attempt_count": expected_count,
            "selection_pool_complete": True,
            "sample_count": sample_count,
            "selected_config_id": selected_id,
            "dsr": dsr,
        }

    psr = probabilistic_sharpe_ratio(
        observed_sharpe_periodic=selected_stats["periodic_sharpe"],
        benchmark_sharpe_periodic=0.0,
        sample_count=sample_count,
        skewness=selected_stats["skewness"],
        pearson_kurtosis=selected_stats["pearson_kurtosis"],
    )

    if selected_stats["periodic_sharpe"] < max(periodic_sharpes):
        warnings.append("selected_trial_is_not_maximum_periodic_sharpe")
    warnings = _ordered_unique(
        warnings
        + list(dsr.get("warnings") or [])
        + list(psr.get("warnings") or [])
    )

    context_output = {
        key: selected_trial["context"][key] for key in _PANEL_CONTEXT_KEYS
    }
    panel_hash_payload = {
        "schema": "complete_sharpe_trial_panel_v1",
        "expected_attempt_count": expected_count,
        "selection_pool_complete": True,
        "expected_return_dates": expected_dates,
        "periods_per_year": periods,
        "selected_config_id": selected_id,
        "context": context_output,
        "trials": [
            {
                "config_id": trial["config_id"],
                "config": trial["config"],
                "return_series": trial["return_series"],
                "return_series_sha256": trial["return_series_sha256"],
                "return_series_source": trial["return_series_source"],
            }
            for trial in normalized_trials
        ],
    }

    annualization_factor = math.sqrt(periods)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "computable",
        "selected_config_id": selected_id,
        "expected_attempt_count": expected_count,
        "selection_pool_complete": True,
        "raw_trial_count": raw_trial_count,
        "sample_count": sample_count,
        "periods_per_year": periods,
        "context": context_output,
        "expected_return_dates_sha256": _stable_hash(
            {"schema": "expected_return_dates_v1", "dates": expected_dates}
        ),
        "panel_sha256": _stable_hash(panel_hash_payload),
        "panel_hash_method": "sha256_canonical_json_v1",
        "date_start": selected_trial["return_series"][0]["date"],
        "date_end": selected_trial["return_series"][-1]["date"],
        "average_pairwise_correlation": average_correlation,
        "average_pairwise_correlation_for_effective_count": correlation_for_count,
        "pairwise_correlations": correlation_rows,
        "effective_independent_trial_count": effective_count,
        "effective_trial_count_method": (
            "bailey_lopez_de_prado_average_correlation_interpolation_v1"
        ),
        "trial_sharpe_sample_std_periodic": trial_sharpe_std,
        "trial_sharpe_dispersion_ddof": 1,
        "trial_sharpes": [
            {
                "config_id": config_id,
                "periodic_sharpe": stats_by_id[config_id]["periodic_sharpe"],
                "annualized_sharpe": (
                    stats_by_id[config_id]["periodic_sharpe"]
                    * annualization_factor
                ),
            }
            for config_id in config_ids
        ],
        "selected_return_series": selected_trial["return_series"],
        "selected_return_series_sha256": _stable_hash(
            {
                "schema": "dated_periodic_return_series_v1",
                "rows": selected_trial["return_series"],
            }
        ),
        "selected_periodic_sharpe": selected_stats["periodic_sharpe"],
        "selected_annualized_sharpe": (
            selected_stats["periodic_sharpe"] * annualization_factor
        ),
        "selected_moments": {
            key: value
            for key, value in selected_stats.items()
            if key not in {"status", "periodic_sharpe"}
        },
        "expected_maximum_sharpe_periodic": dsr[
            "expected_maximum_sharpe_periodic"
        ],
        "expected_maximum_sharpe_annualized": (
            dsr["expected_maximum_sharpe_periodic"] * annualization_factor
        ),
        "psr": psr,
        "dsr": dsr,
        "warnings": warnings,
    }


# A shorter, discoverable alias for callers that already operate on panels.
evaluate_trial_panel = evaluate_deflated_sharpe_trial_panel


__all__ = [
    "EULER_MASCHERONI",
    "build_backtest_sharpe_inference",
    "deflated_sharpe_ratio",
    "evaluate_deflated_sharpe_trial_panel",
    "evaluate_trial_panel",
    "expected_maximum_sharpe",
    "probabilistic_sharpe_ratio",
]
