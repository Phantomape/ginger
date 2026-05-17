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
