"""Tail-aware evaluator gates for strategy and sleeve promotion.

This module intentionally consumes plain metric dictionaries so it can be used
by backtests, live trade journals, pilot-sleeve attribution, and future weekly
promotion reviews without coupling to one runner.
"""

from __future__ import annotations

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
