"""Tail-aware evaluator gates for strategy and sleeve promotion.

This module intentionally consumes plain metric dictionaries so it can be used
by backtests, live trade journals, pilot-sleeve attribution, and future weekly
promotion reviews without coupling to one runner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class GateThresholds:
    min_trades_for_promotion: int = 20
    min_expected_value_usd: float = 0.0
    min_avg_r_multiple: float = 0.0
    min_sharpe_ratio: float = 0.75
    min_tail_ratio: float = 0.80
    min_skewness: float = -1.50
    max_excess_kurtosis: float = 12.0
    max_top_5_contribution_pct: float = 0.60
    max_hhi_concentration: float = 0.35
    max_drawdown_pct: float = 0.12
    max_live_vs_backtest_r_gap: float = 0.50


DEFAULT_THRESHOLDS = GateThresholds()


@dataclass(frozen=True)
class ExperimentGateThresholds:
    min_adjusted_trades: int = 9
    min_adjusted_windows: int = 2
    min_ev_improved_windows: int = 2
    max_ev_regressed_windows: int = 0
    min_aggregate_ev_delta: float = 0.0
    min_aggregate_pnl_delta: float = 0.0
    max_drawdown_worse: float = 0.005
    max_single_ticker_positive_share: float = 0.50
    max_top_5_contribution_pct: float = 0.60
    max_hhi_concentration: float = 0.35
    require_tail_concentration_evidence: bool = True
    require_tail_concentration_not_worse: bool = True
    concentration_tolerance: float = 1e-12


DEFAULT_EXPERIMENT_GATE_THRESHOLDS = ExperimentGateThresholds()


@dataclass(frozen=True)
class PortfolioContributionGateThresholds:
    """Thresholds for the small-sleeve portfolio-contribution lane.

    This is deliberately separate from :class:`ExperimentGateThresholds`.
    The existing experiment gate asks whether a challenger should replace the
    champion.  This v1 gate asks whether the locked capital-neutral 90% core
    plus 10% candidate mix improves the combined portfolio without creating a
    material risk regression.

    Percentage values are fractions: ``0.005`` is 0.5 percentage points of
    drawdown and ``0.05`` is 5% relative ES95 worsening.
    """

    min_aggregate_ev_delta: float = 0.0
    min_aggregate_pnl_delta: float = 0.0
    min_affected_trades: int = 20
    min_affected_windows: int = 2
    required_family_count: int = 31
    min_non_regressed_windows: int = 2
    max_material_regressed_windows: int = 1
    window_ev_materiality_fraction: float = 0.01
    max_drawdown_worse: float = 0.005
    max_es95_worsening_fraction: float = 0.05
    required_candidate_weight: float = 0.10
    required_core_weight: float = 0.90
    weight_tolerance: float = 1e-12
    max_candidate_weight: float = 0.10
    max_single_ticker_positive_share: float = 0.50
    max_top_5_contribution_pct: float = 0.60
    max_hhi_concentration: float = 0.35


DEFAULT_PORTFOLIO_CONTRIBUTION_GATE_THRESHOLDS = (
    PortfolioContributionGateThresholds()
)


PROMOTION_STATES = {"research", "shadow", "pilot", "limited_production", "core"}
DEMOTION_STATES = {"quarantine", "retired"}
STATE_ORDER = {
    "research": 0,
    "shadow": 1,
    "pilot": 2,
    "limited_production": 3,
    "core": 4,
    "quarantine": -1,
    "retired": -2,
}


def _num(metrics: dict[str, Any], key: str, default: float | None = None) -> float | None:
    value = metrics.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(metrics: dict[str, Any], key: str, default: int = 0) -> int:
    value = metrics.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _prefix_value(metrics: dict[str, Any], prefix: str, suffix: str) -> float | None:
    return _num(metrics, f"{prefix}_{suffix}")


def _first_num(
    metrics: dict[str, Any],
    keys: tuple[str, ...],
    default: float | None = None,
) -> float | None:
    for key in keys:
        value = _num(metrics, key)
        if value is not None:
            return value
    return default


def _first_int(
    metrics: dict[str, Any],
    keys: tuple[str, ...],
    default: int = 0,
) -> int:
    for key in keys:
        if key in metrics and metrics.get(key) is not None:
            return _int(metrics, key, default)
    return default


def _first_value(metrics: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in metrics:
            return metrics.get(key)
    return None


def _window_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    try:
        return sorted({str(item) for item in value if str(item or "")})
    except TypeError:
        return []


def evaluate_distribution_gates(
    metrics: dict[str, Any],
    *,
    thresholds: GateThresholds = DEFAULT_THRESHOLDS,
    prefix: str = "r",
) -> tuple[list[str], list[str]]:
    """Return (hard_failures, warnings) for tail shape and concentration.

    `prefix="r"` is preferred because R-multiple normalises position size.
    `prefix="pnl"` can be used for raw dollar P&L diagnostics.
    """
    failures: list[str] = []
    warnings: list[str] = []

    skewness = _prefix_value(metrics, prefix, "skewness")
    if skewness is not None and skewness < thresholds.min_skewness:
        failures.append(f"{prefix}_negative_skew")
    elif skewness is not None and skewness < 0:
        warnings.append(f"{prefix}_mild_negative_skew")

    kurtosis = _prefix_value(metrics, prefix, "excess_kurtosis")
    if kurtosis is not None and kurtosis > thresholds.max_excess_kurtosis:
        failures.append(f"{prefix}_fat_tail_kurtosis")
    elif kurtosis is not None and kurtosis > thresholds.max_excess_kurtosis * 0.75:
        warnings.append(f"{prefix}_elevated_kurtosis")

    tail_ratio = _prefix_value(metrics, prefix, "tail_ratio")
    if tail_ratio is not None and tail_ratio < thresholds.min_tail_ratio:
        failures.append(f"{prefix}_weak_tail_ratio")

    top5 = _prefix_value(metrics, prefix, "top_5_contribution_pct")
    if top5 is not None and top5 > thresholds.max_top_5_contribution_pct:
        failures.append(f"{prefix}_top5_concentration")
    elif top5 is not None and top5 > thresholds.max_top_5_contribution_pct * 0.85:
        warnings.append(f"{prefix}_elevated_top5_concentration")

    hhi = _prefix_value(metrics, prefix, "hhi_concentration")
    if hhi is not None and hhi > thresholds.max_hhi_concentration:
        failures.append(f"{prefix}_hhi_concentration")
    elif hhi is not None and hhi > thresholds.max_hhi_concentration * 0.85:
        warnings.append(f"{prefix}_elevated_hhi")

    return failures, warnings


def evaluate_quality_gates(
    metrics: dict[str, Any],
    *,
    thresholds: GateThresholds = DEFAULT_THRESHOLDS,
) -> tuple[list[str], list[str]]:
    """Return (hard_failures, warnings) for profitability and drawdown quality."""
    failures: list[str] = []
    warnings: list[str] = []

    total_trades = _int(metrics, "total_trades")
    if total_trades < thresholds.min_trades_for_promotion:
        failures.append("insufficient_sample")

    ev = _num(metrics, "expected_value_usd")
    if ev is not None and ev <= thresholds.min_expected_value_usd:
        failures.append("non_positive_expected_value")

    avg_r = _num(metrics, "avg_r_multiple")
    if avg_r is not None and avg_r <= thresholds.min_avg_r_multiple:
        failures.append("non_positive_avg_r")

    sharpe = _num(metrics, "sharpe_ratio")
    if sharpe is not None and sharpe < thresholds.min_sharpe_ratio:
        warnings.append("low_sharpe")

    max_dd_pct = _num(metrics, "max_drawdown_pct")
    if max_dd_pct is not None and max_dd_pct > thresholds.max_drawdown_pct:
        failures.append("drawdown_breach")

    live_r = _num(metrics, "live_avg_r_multiple")
    backtest_r = _num(metrics, "backtest_avg_r_multiple")
    if live_r is not None and backtest_r is not None:
        gap = backtest_r - live_r
        if gap > thresholds.max_live_vs_backtest_r_gap:
            failures.append("live_vs_backtest_decay")
        elif gap > thresholds.max_live_vs_backtest_r_gap * 0.6:
            warnings.append("possible_live_vs_backtest_decay")

    return failures, warnings


def evaluate_metrics(
    metrics: dict[str, Any],
    *,
    thresholds: GateThresholds = DEFAULT_THRESHOLDS,
    prefer_r_multiple: bool = True,
) -> dict[str, Any]:
    """Evaluate a metrics dict and produce a promotion-ready gate report."""
    prefix = "r" if prefer_r_multiple else "pnl"
    quality_failures, quality_warnings = evaluate_quality_gates(
        metrics,
        thresholds=thresholds,
    )
    shape_failures, shape_warnings = evaluate_distribution_gates(
        metrics,
        thresholds=thresholds,
        prefix=prefix,
    )
    failures = quality_failures + shape_failures
    warnings = quality_warnings + shape_warnings

    return {
        "passed": not failures,
        "hard_failures": failures,
        "warnings": warnings,
        "preferred_distribution_prefix": prefix,
        "thresholds": asdict(thresholds),
    }


def evaluate_experiment_promotion_gate(
    metrics: dict[str, Any],
    *,
    thresholds: ExperimentGateThresholds = DEFAULT_EXPERIMENT_GATE_THRESHOLDS,
) -> dict[str, Any]:
    """Evaluate whether a measured experiment is promotion-ready.

    This gate compares a variant against a baseline. It is for experiment
    closeout and default-off sleeve promotion review, not for live order flow.
    """
    failures: list[str] = []
    warnings: list[str] = []

    aggregate_ev_delta = _first_num(
        metrics,
        ("aggregate_ev_delta", "expected_value_score_delta"),
    )
    aggregate_pnl_delta = _first_num(
        metrics,
        ("aggregate_pnl_delta", "total_pnl_delta"),
    )
    windows_ev_improved = _first_num(metrics, ("windows_ev_improved",))
    windows_ev_regressed = _first_num(metrics, ("windows_ev_regressed",))
    max_drawdown_worse = _first_num(
        metrics,
        (
            "max_drawdown_worse_max",
            "max_drawdown_worse",
            "max_drawdown_delta_max",
            "max_drawdown_worsening_max",
            "max_drawdown_worsening",
        ),
    )
    adjusted_trade_count = _first_int(
        metrics,
        (
            "adjusted_trade_count",
            "variant_adjusted_trade_count",
            "paper_adjusted_trade_count",
            "touched_trade_count",
        ),
    )
    adjusted_windows = _window_values(
        _first_value(
            metrics,
            (
                "adjusted_windows",
                "variant_adjusted_windows",
                "paper_adjusted_windows",
                "touched_windows",
            ),
        )
    )
    adjusted_window_count = _first_int(
        metrics,
        ("adjusted_window_count", "variant_adjusted_window_count"),
        default=len(adjusted_windows),
    )

    checks = {
        "positive_aggregate_ev": (
            aggregate_ev_delta is not None
            and aggregate_ev_delta > thresholds.min_aggregate_ev_delta
        ),
        "positive_aggregate_pnl": (
            aggregate_pnl_delta is not None
            and aggregate_pnl_delta > thresholds.min_aggregate_pnl_delta
        ),
        "ev_improved_window_coverage": (
            windows_ev_improved is not None
            and windows_ev_improved >= thresholds.min_ev_improved_windows
        ),
        "no_ev_regressed_windows": (
            windows_ev_regressed is not None
            and windows_ev_regressed <= thresholds.max_ev_regressed_windows
        ),
        "adjusted_trade_sample": (
            adjusted_trade_count >= thresholds.min_adjusted_trades
        ),
        "adjusted_window_coverage": (
            adjusted_window_count >= thresholds.min_adjusted_windows
        ),
        "drawdown_worse_guard": (
            max_drawdown_worse is not None
            and max_drawdown_worse <= thresholds.max_drawdown_worse
        ),
    }

    if aggregate_ev_delta is None:
        failures.append("missing_aggregate_ev_delta")
    elif not checks["positive_aggregate_ev"]:
        failures.append("non_positive_aggregate_ev")

    if aggregate_pnl_delta is None:
        failures.append("missing_aggregate_pnl_delta")
    elif not checks["positive_aggregate_pnl"]:
        failures.append("non_positive_aggregate_pnl")

    if windows_ev_improved is None:
        failures.append("missing_windows_ev_improved")
    elif not checks["ev_improved_window_coverage"]:
        failures.append("insufficient_ev_improved_windows")

    if windows_ev_regressed is None:
        failures.append("missing_windows_ev_regressed")
    elif not checks["no_ev_regressed_windows"]:
        failures.append("ev_regressed_windows")

    if not checks["adjusted_trade_sample"]:
        failures.append("insufficient_adjusted_sample")
    if not checks["adjusted_window_coverage"]:
        failures.append("insufficient_adjusted_window_coverage")

    if max_drawdown_worse is None:
        failures.append("missing_drawdown_delta")
    elif not checks["drawdown_worse_guard"]:
        failures.append("drawdown_worse_guardrail")

    concentration_specs = (
        (
            "single_ticker_positive_share",
            (
                "single_ticker_positive_share",
                "single_ticker_positive_pnl_share",
            ),
            (
                "baseline_single_ticker_positive_share",
                "baseline_single_ticker_positive_pnl_share",
            ),
            thresholds.max_single_ticker_positive_share,
        ),
        (
            "top_5_contribution_pct",
            (
                "top_5_contribution_pct",
                "r_top_5_contribution_pct",
                "pnl_top_5_contribution_pct",
            ),
            (
                "baseline_top_5_contribution_pct",
                "baseline_r_top_5_contribution_pct",
                "baseline_pnl_top_5_contribution_pct",
            ),
            thresholds.max_top_5_contribution_pct,
        ),
        (
            "hhi_concentration",
            (
                "hhi_concentration",
                "r_hhi_concentration",
                "pnl_hhi_concentration",
            ),
            (
                "baseline_hhi_concentration",
                "baseline_r_hhi_concentration",
                "baseline_pnl_hhi_concentration",
            ),
            thresholds.max_hhi_concentration,
        ),
    )
    concentration_checks = []
    concentration_present = False
    concentration_comparable = False
    concentration_cap_passed = True
    concentration_not_worse = True

    for name, value_keys, baseline_keys, max_allowed in concentration_specs:
        value = _first_num(metrics, value_keys)
        baseline = _first_num(metrics, baseline_keys)
        row = {
            "name": name,
            "value": value,
            "baseline": baseline,
            "max_allowed": max_allowed,
            "delta": None,
            "cap_passed": None,
            "not_worse": None,
        }
        if value is not None:
            concentration_present = True
            row["cap_passed"] = value <= max_allowed
            if not row["cap_passed"]:
                concentration_cap_passed = False
                failures.append(f"{name}_cap")
            if baseline is not None:
                concentration_comparable = True
                row["delta"] = round(value - baseline, 12)
                row["not_worse"] = value <= baseline + thresholds.concentration_tolerance
                if not row["not_worse"]:
                    concentration_not_worse = False
                    failures.append(f"{name}_worse")
            else:
                warnings.append(f"missing_{name}_baseline")
        concentration_checks.append(row)

    if thresholds.require_tail_concentration_evidence and not concentration_present:
        failures.append("missing_tail_concentration_evidence")
    if (
        thresholds.require_tail_concentration_not_worse
        and concentration_present
        and not concentration_comparable
    ):
        failures.append("missing_tail_concentration_baseline")

    checks.update(
        {
            "tail_concentration_evidence": (
                concentration_present
                or not thresholds.require_tail_concentration_evidence
            ),
            "tail_concentration_cap": concentration_cap_passed,
            "tail_concentration_not_worse": (
                concentration_not_worse
                and (
                    concentration_comparable
                    or not thresholds.require_tail_concentration_not_worse
                )
            ),
        }
    )

    return {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
        "warnings": warnings,
        "checks": checks,
        "metrics": {
            "aggregate_ev_delta": aggregate_ev_delta,
            "aggregate_pnl_delta": aggregate_pnl_delta,
            "windows_ev_improved": windows_ev_improved,
            "windows_ev_regressed": windows_ev_regressed,
            "adjusted_trade_count": adjusted_trade_count,
            "adjusted_windows": adjusted_windows,
            "adjusted_window_count": adjusted_window_count,
            "max_drawdown_worse": max_drawdown_worse,
        },
        "concentration_checks": concentration_checks,
        "thresholds": asdict(thresholds),
    }


def evaluate_portfolio_contribution_gate(
    metrics: dict[str, Any],
    *,
    thresholds: PortfolioContributionGateThresholds = (
        DEFAULT_PORTFOLIO_CONTRIBUTION_GATE_THRESHOLDS
    ),
) -> dict[str, Any]:
    """Evaluate a small sleeve's *portfolio* contribution.

    Unlike :func:`evaluate_experiment_promotion_gate`, this is not a champion
    replacement test.  It evaluates a capital-neutral combined portfolio and
    deliberately distinguishes three outcomes:

    ``portfolio_reject``
        Observed economics or risk violates a hard boundary.
    ``portfolio_forward_watch``
        No hard failure is observed, but measurement, sample, or
        multiple-testing evidence is incomplete.
    ``accepted_portfolio_paper``
        Economics, risk, sample, and simultaneous-panel evidence all pass.

    Expected caller-supplied fields
    -------------------------------
    ``window_contributions`` is a mapping keyed by window.  Each row must
    contain ``core_ev``, ``ev_delta``, and ``pnl_delta``.  A window is a
    material regression only when EV and PnL are both negative and the EV
    loss exceeds ``window_ev_materiality_fraction`` of ``abs(core_ev)``.

    ``es95_worsening_fraction`` is a relative worsening fraction, not a
    percentage-point value.  ``family_batch_complete`` plus matching
    31-family expected/observed counts is distinct from the wider historical
    selection panel.  ``selection_panel_complete``,
    ``multiple_testing_passed``, and a positive
    ``simultaneous_ev_delta_lower_bound`` are required for paper acceptance.
    The caller owns the paired/simultaneous statistical calculation; this
    read-only gate only validates its declared result.
    """

    hard_failures: list[str] = []
    measurement_blockers: list[str] = []
    statistical_blockers: list[str] = []
    warnings: list[str] = []

    def finite_num(keys: tuple[str, ...]) -> float | None:
        for key in keys:
            value = metrics.get(key)
            if value is None or isinstance(value, bool):
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                return number
        return None

    # Capital neutrality is a measurement contract.  A missing/false
    # declaration cannot establish that the candidate improved the portfolio,
    # but it is not evidence that the candidate's alpha is economically bad.
    capital_neutral_raw = _first_value(
        metrics,
        ("capital_neutral", "equal_capital", "is_capital_neutral"),
    )
    capital_neutral = capital_neutral_raw is True
    if capital_neutral_raw is None:
        measurement_blockers.append("missing_capital_neutrality")
    elif not capital_neutral:
        measurement_blockers.append("capital_not_neutral")

    candidate_weight = finite_num(
        ("candidate_weight", "sleeve_weight", "portfolio_candidate_weight")
    )
    if candidate_weight is None:
        measurement_blockers.append("missing_candidate_weight")
    elif candidate_weight <= 0.0:
        measurement_blockers.append("candidate_weight_not_positive")
    elif candidate_weight > thresholds.max_candidate_weight:
        hard_failures.append("candidate_weight_cap")
    elif not math.isclose(
        candidate_weight,
        thresholds.required_candidate_weight,
        rel_tol=0.0,
        abs_tol=thresholds.weight_tolerance,
    ):
        measurement_blockers.append("candidate_weight_not_fixed")

    core_weight = finite_num(("core_weight", "portfolio_core_weight"))
    if core_weight is None:
        measurement_blockers.append("missing_core_weight")
    elif not math.isclose(
        core_weight,
        thresholds.required_core_weight,
        rel_tol=0.0,
        abs_tol=thresholds.weight_tolerance,
    ):
        measurement_blockers.append("core_weight_not_fixed")

    portfolio_weight_sum = finite_num(
        ("portfolio_weight_sum", "weight_sum", "total_weight")
    )
    if portfolio_weight_sum is None:
        measurement_blockers.append("missing_portfolio_weight_sum")
    elif not math.isclose(
        portfolio_weight_sum,
        1.0,
        rel_tol=0.0,
        abs_tol=thresholds.weight_tolerance,
    ):
        measurement_blockers.append("portfolio_weight_sum_not_one")

    aggregate_ev_delta = finite_num(
        ("aggregate_ev_delta", "expected_value_score_delta")
    )
    if aggregate_ev_delta is None:
        measurement_blockers.append("missing_aggregate_ev_delta")
    elif aggregate_ev_delta <= thresholds.min_aggregate_ev_delta:
        hard_failures.append("non_positive_aggregate_ev")

    aggregate_pnl_delta = finite_num(
        ("aggregate_pnl_delta", "total_pnl_delta")
    )
    if aggregate_pnl_delta is None:
        measurement_blockers.append("missing_aggregate_pnl_delta")
    elif aggregate_pnl_delta <= thresholds.min_aggregate_pnl_delta:
        hard_failures.append("non_positive_aggregate_pnl")

    affected_trade_raw = _first_value(
        metrics,
        (
            "affected_trade_count",
            "touched_trade_count",
            "adjusted_trade_count",
            "variant_adjusted_trade_count",
        ),
    )
    affected_trade_count: int | None = None
    if (
        affected_trade_raw is not None
        and not isinstance(affected_trade_raw, bool)
    ):
        try:
            parsed_trade_count = int(affected_trade_raw)
        except (TypeError, ValueError, OverflowError):
            parsed_trade_count = -1
        if parsed_trade_count >= 0:
            affected_trade_count = parsed_trade_count
    if affected_trade_count is None:
        measurement_blockers.append("missing_affected_trade_count")
    elif affected_trade_count < thresholds.min_affected_trades:
        measurement_blockers.append("insufficient_affected_sample")

    raw_window_contributions = _first_value(
        metrics,
        ("window_contributions", "portfolio_window_contributions"),
    )
    window_items: list[tuple[str, Any]] = []
    if isinstance(raw_window_contributions, dict):
        window_items = sorted(
            (
                (str(name), row)
                for name, row in raw_window_contributions.items()
                if str(name or "")
            ),
            key=lambda item: item[0],
        )
    elif isinstance(raw_window_contributions, (list, tuple)):
        for index, row in enumerate(raw_window_contributions):
            if isinstance(row, dict):
                name = str(row.get("window") or row.get("name") or index)
            else:
                name = str(index)
            window_items.append((name, row))
    else:
        measurement_blockers.append("missing_window_contributions")

    window_checks: list[dict[str, Any]] = []
    valid_window_count = 0
    material_regressed_windows = 0
    for window_name, raw_row in window_items:
        if not isinstance(raw_row, dict):
            measurement_blockers.append(
                f"invalid_window_contribution:{window_name}"
            )
            window_checks.append(
                {
                    "window": window_name,
                    "valid": False,
                    "core_ev": None,
                    "ev_delta": None,
                    "pnl_delta": None,
                    "ev_delta_fraction_of_core": None,
                    "material_regression": None,
                }
            )
            continue

        def row_num(keys: tuple[str, ...]) -> float | None:
            for key in keys:
                value = raw_row.get(key)
                if isinstance(value, bool):
                    continue
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(number):
                    return number
            return None

        core_ev = row_num(
            (
                "core_ev",
                "baseline_ev",
                "core_expected_value_score",
                "baseline_expected_value_score",
            )
        )
        ev_delta = row_num(("ev_delta", "expected_value_score_delta"))
        pnl_delta = row_num(("pnl_delta", "total_pnl_delta"))
        valid = core_ev is not None and ev_delta is not None and pnl_delta is not None
        ev_fraction: float | None = None
        material_regression: bool | None = None

        if valid:
            valid_window_count += 1
            if abs(core_ev) > 1e-15:
                ev_fraction = abs(ev_delta) / abs(core_ev)
            material_regression = bool(
                ev_delta < 0.0
                and pnl_delta < 0.0
                and (
                    ev_fraction is None
                    or ev_fraction > thresholds.window_ev_materiality_fraction
                )
            )
            if material_regression:
                material_regressed_windows += 1
        else:
            measurement_blockers.append(
                f"invalid_window_contribution:{window_name}"
            )

        window_checks.append(
            {
                "window": window_name,
                "valid": valid,
                "core_ev": core_ev,
                "ev_delta": ev_delta,
                "pnl_delta": pnl_delta,
                "ev_delta_fraction_of_core": ev_fraction,
                "material_regression": material_regression,
            }
        )

    affected_window_raw = _first_value(
        metrics,
        (
            "affected_window_count",
            "touched_window_count",
            "adjusted_window_count",
            "variant_adjusted_window_count",
        ),
    )
    affected_window_count: int | None = None
    if affected_window_raw is None:
        affected_window_count = valid_window_count
    elif not isinstance(affected_window_raw, bool):
        try:
            parsed_window_count = int(affected_window_raw)
        except (TypeError, ValueError, OverflowError):
            parsed_window_count = -1
        if parsed_window_count >= 0:
            affected_window_count = parsed_window_count

    if affected_window_count is None:
        measurement_blockers.append("missing_affected_window_count")
    else:
        if affected_window_count != valid_window_count:
            measurement_blockers.append("affected_window_count_mismatch")
        if affected_window_count < thresholds.min_affected_windows:
            measurement_blockers.append("insufficient_affected_window_coverage")

    non_regressed_window_count = valid_window_count - material_regressed_windows
    complete_window_evidence = (
        valid_window_count >= thresholds.min_affected_windows
        and affected_window_count == valid_window_count
        and all(row["valid"] for row in window_checks)
    )
    if material_regressed_windows > thresholds.max_material_regressed_windows:
        hard_failures.append("too_many_material_regressed_windows")
    if complete_window_evidence:
        if non_regressed_window_count < thresholds.min_non_regressed_windows:
            hard_failures.append("insufficient_non_regressed_windows")

    max_drawdown_worse = finite_num(
        (
            "max_drawdown_worse_max",
            "max_drawdown_worse",
            "max_drawdown_delta_max",
            "max_drawdown_worsening_max",
            "max_drawdown_worsening",
        )
    )
    if max_drawdown_worse is None:
        measurement_blockers.append("missing_drawdown_delta")
    elif max_drawdown_worse > thresholds.max_drawdown_worse:
        hard_failures.append("drawdown_worse_guardrail")

    es95_worsening_fraction = finite_num(
        (
            "es95_worsening_fraction",
            "expected_shortfall_95_worsening_fraction",
            "es_95_worsening_fraction",
        )
    )
    if es95_worsening_fraction is None:
        measurement_blockers.append("missing_es95_worsening_fraction")
    elif es95_worsening_fraction > thresholds.max_es95_worsening_fraction:
        hard_failures.append("es95_worse_guardrail")

    concentration_specs = (
        (
            "single_ticker_positive_share",
            (
                "single_ticker_positive_share",
                "single_ticker_positive_pnl_share",
                "portfolio_single_ticker_positive_share",
            ),
            thresholds.max_single_ticker_positive_share,
        ),
        (
            "top_5_contribution_pct",
            (
                "top_5_contribution_pct",
                "pnl_top_5_contribution_pct",
                "portfolio_top_5_contribution_pct",
            ),
            thresholds.max_top_5_contribution_pct,
        ),
        (
            "hhi_concentration",
            (
                "hhi_concentration",
                "pnl_hhi_concentration",
                "portfolio_hhi_concentration",
            ),
            thresholds.max_hhi_concentration,
        ),
    )
    concentration_checks: list[dict[str, Any]] = []
    for name, keys, max_allowed in concentration_specs:
        value = finite_num(keys)
        cap_passed: bool | None = None
        if value is None or value < 0.0:
            measurement_blockers.append(f"missing_{name}")
        else:
            cap_passed = value <= max_allowed
            if not cap_passed:
                hard_failures.append(f"{name}_cap")
        concentration_checks.append(
            {
                "name": name,
                "value": value,
                "max_allowed": max_allowed,
                "cap_passed": cap_passed,
            }
        )

    family_batch_raw = _first_value(
        metrics,
        ("family_batch_complete", "candidate_batch_complete"),
    )
    family_batch_complete = family_batch_raw is True

    def nonnegative_int(keys: tuple[str, ...]) -> int | None:
        raw = _first_value(metrics, keys)
        if raw is None or isinstance(raw, bool):
            return None
        try:
            parsed = int(raw)
        except (TypeError, ValueError, OverflowError):
            return None
        return parsed if parsed >= 0 else None

    expected_family_count = nonnegative_int(
        ("expected_family_count", "family_count_expected")
    )
    observed_family_count = nonnegative_int(
        ("observed_family_count", "family_count_observed", "candidate_count")
    )
    if not family_batch_complete:
        statistical_blockers.append("family_batch_incomplete")
    if expected_family_count is None:
        statistical_blockers.append("missing_expected_family_count")
    elif expected_family_count != thresholds.required_family_count:
        statistical_blockers.append("unexpected_family_batch_scope")
    if observed_family_count is None:
        statistical_blockers.append("missing_observed_family_count")
    elif (
        expected_family_count is not None
        and observed_family_count != expected_family_count
    ):
        statistical_blockers.append("family_count_mismatch")

    selection_panel_raw = _first_value(
        metrics,
        ("selection_panel_complete", "panel_complete"),
    )
    selection_panel_complete = selection_panel_raw is True
    if not selection_panel_complete:
        statistical_blockers.append("selection_panel_incomplete")

    multiple_testing_raw = _first_value(
        metrics,
        ("multiple_testing_passed", "simultaneous_test_passed"),
    )
    multiple_testing_passed = multiple_testing_raw is True
    if not multiple_testing_passed:
        statistical_blockers.append("multiple_testing_not_passed")

    simultaneous_ev_delta_lower_bound = finite_num(
        (
            "simultaneous_ev_delta_lower_bound",
            "simultaneous_lower_bound_ev_delta",
            "familywise_ev_delta_lower_bound",
        )
    )
    if simultaneous_ev_delta_lower_bound is None:
        statistical_blockers.append("missing_simultaneous_ev_delta_lower_bound")
    elif simultaneous_ev_delta_lower_bound <= thresholds.min_aggregate_ev_delta:
        statistical_blockers.append("simultaneous_ev_lower_bound_not_positive")

    evidence_blockers = measurement_blockers + statistical_blockers
    if hard_failures:
        portfolio_verdict = "portfolio_reject"
        status = "blocked"
    elif evidence_blockers:
        portfolio_verdict = "portfolio_forward_watch"
        status = "watch"
    else:
        portfolio_verdict = "accepted_portfolio_paper"
        status = "passed"

    checks = {
        "capital_neutral": capital_neutral,
        "candidate_weight_cap": (
            candidate_weight is not None
            and 0.0 < candidate_weight <= thresholds.max_candidate_weight
        ),
        "fixed_capital_weights": (
            candidate_weight is not None
            and core_weight is not None
            and portfolio_weight_sum is not None
            and math.isclose(
                candidate_weight,
                thresholds.required_candidate_weight,
                rel_tol=0.0,
                abs_tol=thresholds.weight_tolerance,
            )
            and math.isclose(
                core_weight,
                thresholds.required_core_weight,
                rel_tol=0.0,
                abs_tol=thresholds.weight_tolerance,
            )
            and math.isclose(
                portfolio_weight_sum,
                1.0,
                rel_tol=0.0,
                abs_tol=thresholds.weight_tolerance,
            )
        ),
        "positive_aggregate_ev": (
            aggregate_ev_delta is not None
            and aggregate_ev_delta > thresholds.min_aggregate_ev_delta
        ),
        "positive_aggregate_pnl": (
            aggregate_pnl_delta is not None
            and aggregate_pnl_delta > thresholds.min_aggregate_pnl_delta
        ),
        "affected_trade_sample": (
            affected_trade_count is not None
            and affected_trade_count >= thresholds.min_affected_trades
        ),
        "affected_window_coverage": (
            affected_window_count is not None
            and affected_window_count >= thresholds.min_affected_windows
            and affected_window_count == valid_window_count
        ),
        "material_window_regression_guard": (
            complete_window_evidence
            and material_regressed_windows
            <= thresholds.max_material_regressed_windows
            and non_regressed_window_count >= thresholds.min_non_regressed_windows
        ),
        "drawdown_worse_guard": (
            max_drawdown_worse is not None
            and max_drawdown_worse <= thresholds.max_drawdown_worse
        ),
        "es95_worse_guard": (
            es95_worsening_fraction is not None
            and es95_worsening_fraction <= thresholds.max_es95_worsening_fraction
        ),
        "concentration_caps": all(
            row["cap_passed"] is True for row in concentration_checks
        ),
        "family_batch_complete": (
            family_batch_complete
            and expected_family_count == thresholds.required_family_count
            and observed_family_count == expected_family_count
        ),
        "selection_panel_complete": selection_panel_complete,
        "multiple_testing_passed": multiple_testing_passed,
        "simultaneous_ev_lower_bound_positive": (
            simultaneous_ev_delta_lower_bound is not None
            and simultaneous_ev_delta_lower_bound
            > thresholds.min_aggregate_ev_delta
        ),
    }

    return {
        "passed": portfolio_verdict == "accepted_portfolio_paper",
        "status": status,
        "portfolio_verdict": portfolio_verdict,
        "hard_failures": hard_failures,
        "evidence_blockers": evidence_blockers,
        "measurement_blockers": measurement_blockers,
        "statistical_blockers": statistical_blockers,
        "warnings": warnings,
        "checks": checks,
        "metrics": {
            "capital_neutral": capital_neutral_raw,
            "candidate_weight": candidate_weight,
            "core_weight": core_weight,
            "portfolio_weight_sum": portfolio_weight_sum,
            "aggregate_ev_delta": aggregate_ev_delta,
            "aggregate_pnl_delta": aggregate_pnl_delta,
            "affected_trade_count": affected_trade_count,
            "affected_window_count": affected_window_count,
            "valid_window_count": valid_window_count,
            "material_regressed_windows": material_regressed_windows,
            "non_regressed_window_count": non_regressed_window_count,
            "max_drawdown_worse": max_drawdown_worse,
            "es95_worsening_fraction": es95_worsening_fraction,
            "family_batch_complete": family_batch_raw,
            "expected_family_count": expected_family_count,
            "observed_family_count": observed_family_count,
            "selection_panel_complete": selection_panel_complete,
            "multiple_testing_passed": multiple_testing_passed,
            "simultaneous_ev_delta_lower_bound": (
                simultaneous_ev_delta_lower_bound
            ),
        },
        "window_checks": window_checks,
        "concentration_checks": concentration_checks,
        "thresholds": asdict(thresholds),
    }


def recommended_state_transition(
    current_state: str,
    gate_report: dict[str, Any],
    *,
    allow_promotion: bool = True,
) -> str:
    """Recommend one-step state transition from a gate report.

    This is deliberately conservative: hard failures demote or freeze; passing
    gates promote by at most one state per review cycle.
    """
    state = str(current_state or "research")
    failures = set(gate_report.get("hard_failures") or [])

    if "drawdown_breach" in failures or "live_vs_backtest_decay" in failures:
        return "quarantine"
    if state == "retired":
        return "retired"
    if failures:
        if state in {"core", "limited_production"}:
            return "pilot"
        return state
    if not allow_promotion:
        return state

    if state == "research":
        return "shadow"
    if state == "shadow":
        return "pilot"
    if state == "pilot":
        return "limited_production"
    if state == "limited_production":
        return "core"
    return state
