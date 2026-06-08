"""Full-stack candidate-pool experiment verdict helper.

Purpose
-------
Let a SINGLE candidate-pool experiment reach a production / paper-sleeve
verdict instead of being split across many rounds (scout -> shared helper ->
daily wiring -> envelope -> activation). It composes the already-canonical
Gate-4 logic in ``quant.evaluator_gates`` with a codified Gate-5
live-readiness check and an explicit, declared execution envelope.

Verdict ladder
--------------
- ``reject``                         : Gate 4 fails (EV/PnL/window-robustness/
                                       concentration/drawdown/materiality).
- ``accepted_paper_pending_forward`` : Gate 4 passes. Accept as a default-off
                                       paper sleeve NOW. The only things left
                                       before live capital are forward-row
                                       maturation and kill-switch parity --
                                       both of which are designed in THIS same
                                       experiment, so no new experiment is
                                       needed, only calendar time.
- ``live_eligible``                  : Gate 4 + Gate 5 both pass; turning on
                                       live capital is a config change, not a
                                       new alpha search.

Design decisions (confirmed with the operator)
----------------------------------------------
1. A first one-shot experiment whose Gate 4 passes but whose forward rows are
   still immature lands at ``accepted_paper_pending_forward`` -- it is an
   accepted paper sleeve, not a mere "lead".
2. An incomplete execution envelope blocks ``live_eligible`` only. It does NOT
   block ``accepted_paper_pending_forward``; it surfaces as a checklist of
   what still has to be filled before live promotion.

This module is read-only evaluation. It changes no orders, sleeves, sizing,
or ranking. It only turns measured metrics into a standardized verdict.

No JavaScript was used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quant.evaluator_gates import (
    DEFAULT_EXPERIMENT_GATE_THRESHOLDS,
    ExperimentGateThresholds,
    evaluate_experiment_promotion_gate,
)

# Scout materiality floor (AGENTS.md Gate 4): reject when BOTH the average
# per-trade PnL improvement is < $500 AND the average return improvement is
# < 5 percentage points, even if all three windows improve.
MIN_AVG_PNL_PER_TRADE_DELTA = 500.0
MIN_AVG_RETURN_DELTA_PP = 5.0

# Gate 5 (AGENTS.md): a default-off paper sleeve needs at least this many
# closed forward 10-day paper trades before live activation is considered.
MIN_CLOSED_FORWARD_TRADES = 30


def _get(metrics: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    """Return the first present, numeric value among ``keys``."""
    for key in keys:
        value = metrics.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return None


@dataclass
class ExecutionEnvelope:
    """The live-realistic execution parameters a full-stack experiment must
    declare and measure up front, so live promotion is a checklist rather than
    a fresh alpha search.

    Every field listed in ``REQUIRED_FOR_LIVE`` must be set (non-None) before a
    sleeve can become ``live_eligible``. They may be left unset while the sleeve
    is still ``accepted_paper_pending_forward`` -- ``missing()`` then reports the
    remaining checklist.
    """

    base_notional: float | None = None
    max_capital_pct: float | None = None
    min_dollar_volume: float | None = None
    slippage_bps: float | None = None
    max_displacement: int | None = None
    max_concurrent: int | None = None
    order_semantics: str | None = None
    kill_switch_drawdown_pct: float | None = None
    sleeve_drawdown_stop_pct: float | None = None
    notes: str | None = None

    REQUIRED_FOR_LIVE: tuple[str, ...] = field(
        default=(
            "base_notional",
            "max_capital_pct",
            "min_dollar_volume",
            "slippage_bps",
            "max_displacement",
            "max_concurrent",
            "order_semantics",
            "kill_switch_drawdown_pct",
            "sleeve_drawdown_stop_pct",
        ),
        repr=False,
        compare=False,
    )

    def missing(self) -> list[str]:
        """Return the ``REQUIRED_FOR_LIVE`` fields still unset."""
        out: list[str] = []
        for name in self.REQUIRED_FOR_LIVE:
            value = getattr(self, name)
            if value is None or (isinstance(value, str) and not value.strip()):
                out.append(name)
        return out

    def complete(self) -> bool:
        return not self.missing()

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_notional": self.base_notional,
            "max_capital_pct": self.max_capital_pct,
            "min_dollar_volume": self.min_dollar_volume,
            "slippage_bps": self.slippage_bps,
            "max_displacement": self.max_displacement,
            "max_concurrent": self.max_concurrent,
            "order_semantics": self.order_semantics,
            "kill_switch_drawdown_pct": self.kill_switch_drawdown_pct,
            "sleeve_drawdown_stop_pct": self.sleeve_drawdown_stop_pct,
            "notes": self.notes,
            "missing": self.missing(),
            "complete": self.complete(),
        }


def evaluate_materiality(metrics: dict[str, Any]) -> dict[str, Any]:
    """Apply the AGENTS.md scout materiality floor.

    Material when the average per-trade PnL improvement is >= $500 OR the
    average return improvement is >= 5pp. Immaterial only when BOTH fall below
    their floors. If neither figure is supplied, materiality is treated as
    unknown (``material=True`` with a warning) so it never silently blocks.
    """
    avg_pnl = _get(
        metrics,
        ("avg_pnl_per_trade_delta", "avg_pnl_per_trade", "mean_pnl_per_trade_delta"),
    )
    avg_ret_pp = _get(
        metrics,
        (
            "avg_return_delta_pp",
            "avg_return_improvement_pp",
            "mean_return_delta_pp",
        ),
    )
    warnings: list[str] = []
    if avg_pnl is None and avg_ret_pp is None:
        warnings.append("missing_materiality_metrics")
        material = True
    else:
        pnl_material = avg_pnl is not None and avg_pnl >= MIN_AVG_PNL_PER_TRADE_DELTA
        ret_material = avg_ret_pp is not None and avg_ret_pp >= MIN_AVG_RETURN_DELTA_PP
        material = bool(pnl_material or ret_material)
    return {
        "material": material,
        "avg_pnl_per_trade_delta": avg_pnl,
        "avg_return_delta_pp": avg_ret_pp,
        "min_avg_pnl_per_trade_delta": MIN_AVG_PNL_PER_TRADE_DELTA,
        "min_avg_return_delta_pp": MIN_AVG_RETURN_DELTA_PP,
        "warnings": warnings,
    }


def evaluate_gate4(
    window_metrics: dict[str, Any],
    *,
    thresholds: ExperimentGateThresholds = DEFAULT_EXPERIMENT_GATE_THRESHOLDS,
    check_materiality: bool = True,
) -> dict[str, Any]:
    """Canonical Gate 4 = ``evaluate_experiment_promotion_gate`` (EV/PnL,
    window robustness, drawdown-worse guard, single-ticker/top-5/HHI
    concentration) plus the scout materiality floor.
    """
    promo = evaluate_experiment_promotion_gate(window_metrics, thresholds=thresholds)
    failures = list(promo.get("hard_failures", []))
    warnings = list(promo.get("warnings", []))

    materiality: dict[str, Any] | None = None
    if check_materiality:
        materiality = evaluate_materiality(window_metrics)
        warnings.extend(materiality.get("warnings", []))
        if not materiality["material"]:
            failures.append("immaterial_effect")

    return {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
        "warnings": warnings,
        "promotion_gate": promo,
        "materiality": materiality,
    }


def evaluate_live_readiness(
    *,
    envelope: ExecutionEnvelope | None,
    closed_forward_trades: int | None = None,
    forward_pnl: float | None = None,
    replacement_value_passed: bool | None = None,
    kill_switch_parity_passed: bool | None = None,
    min_closed_forward_trades: int = MIN_CLOSED_FORWARD_TRADES,
) -> dict[str, Any]:
    """Codified Gate 5 (AGENTS.md paper-sleeve activation prerequisites).

    A sleeve is live-ready only when all hold:
      - >= ``min_closed_forward_trades`` closed forward 10-day paper trades,
      - positive forward paper PnL,
      - replacement value vs core / cash passed,
      - the execution envelope is complete, and
      - the kill switch + sleeve drawdown stop passed parity tests.

    On a first one-shot experiment, forward rows are typically immature, so this
    normally reports ``ready=False`` with ``blockers``. That is the expected,
    honest state; the caller maps it to ``accepted_paper_pending_forward``.
    """
    blockers: list[str] = []

    n = closed_forward_trades or 0
    if n < min_closed_forward_trades:
        blockers.append(f"forward_rows_immature:{n}/{min_closed_forward_trades}")

    if forward_pnl is None or forward_pnl <= 0:
        blockers.append("forward_pnl_not_positive")

    if not replacement_value_passed:
        blockers.append("replacement_value_not_passed")

    if envelope is None:
        envelope_missing = ["execution_envelope_undeclared"]
    else:
        envelope_missing = envelope.missing()
    if envelope_missing:
        blockers.append("execution_envelope_incomplete")

    if not kill_switch_parity_passed:
        blockers.append("kill_switch_parity_not_passed")

    return {
        "ready": not blockers,
        "blockers": blockers,
        "closed_forward_trades": n,
        "min_closed_forward_trades": min_closed_forward_trades,
        "forward_pnl": forward_pnl,
        "replacement_value_passed": bool(replacement_value_passed),
        "kill_switch_parity_passed": bool(kill_switch_parity_passed),
        "envelope_missing": envelope_missing,
    }


def _next_step(verdict: str, live_readiness: dict[str, Any]) -> str:
    if verdict == "reject":
        return (
            "Roll back the sleeve change and log the failure. Gate 4 did not "
            "pass; do not retune on the frozen sample."
        )
    if verdict == "live_eligible":
        return (
            "Gate 4 + Gate 5 both pass. Live activation is a config/flag change, "
            "not a new alpha experiment -- enable behind the declared envelope "
            "and kill switch."
        )
    # accepted_paper_pending_forward
    remaining = ", ".join(live_readiness.get("blockers", [])) or "none"
    return (
        "Accept as a default-off paper sleeve now. No new experiment is needed "
        "to reach live -- only resolve the remaining Gate-5 items as forward "
        f"evidence matures: {remaining}."
    )


def full_stack_verdict(
    *,
    gate4: dict[str, Any],
    live_readiness: dict[str, Any],
    envelope: ExecutionEnvelope | None = None,
) -> dict[str, Any]:
    """Combine Gate 4 + Gate-5 live-readiness into the verdict ladder.

    - Gate 4 fails               -> ``reject``
    - Gate 4 passes, not live    -> ``accepted_paper_pending_forward``
    - Gate 4 passes, live-ready  -> ``live_eligible``
    """
    if not gate4.get("passed"):
        verdict = "reject"
    elif live_readiness.get("ready"):
        verdict = "live_eligible"
    else:
        verdict = "accepted_paper_pending_forward"

    return {
        "anti_js": "No JavaScript was used.",
        "verdict": verdict,
        "gate4_passed": bool(gate4.get("passed")),
        "live_ready": bool(live_readiness.get("ready")),
        "next_step": _next_step(verdict, live_readiness),
        "gate4": gate4,
        "live_readiness": live_readiness,
        "execution_envelope": envelope.to_dict() if envelope is not None else None,
    }
