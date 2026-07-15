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
                                       maturation, kill-switch parity, and a
                                       complete Deflated-Sharpe report. These
                                       are Gate-5 evidence, not new alpha
                                       search.
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

import math
from dataclasses import dataclass, field
from typing import Any

from quant.evaluator_gates import (
    DEFAULT_EXPERIMENT_GATE_THRESHOLDS,
    DEFAULT_PORTFOLIO_CONTRIBUTION_GATE_THRESHOLDS,
    ExperimentGateThresholds,
    PortfolioContributionGateThresholds,
    evaluate_experiment_promotion_gate,
    evaluate_portfolio_contribution_gate,
)


EVALUATION_MODE_CHAMPION_REPLACEMENT = "champion_replacement"
EVALUATION_MODE_PORTFOLIO_CONTRIBUTION = "portfolio_contribution"
VALID_EVALUATION_MODES = {
    EVALUATION_MODE_CHAMPION_REPLACEMENT,
    EVALUATION_MODE_PORTFOLIO_CONTRIBUTION,
}

# Scout materiality floor (AGENTS.md Gate 4): reject when BOTH the average
# per-trade PnL improvement is < $500 AND the average return improvement is
# < 5 percentage points, even if all three windows improve.
MIN_AVG_PNL_PER_TRADE_DELTA = 500.0
MIN_AVG_RETURN_DELTA_PP = 5.0

# Gate 5 (AGENTS.md): a default-off paper sleeve needs at least this many
# closed forward 10-day paper trades before live activation is considered.
MIN_CLOSED_FORWARD_TRADES = 30

# Gate 5 statistical-selection guard. A strategy may remain default-off paper
# without this evidence, but it cannot become live-eligible until the DSR
# calculation covers the complete declared selection pool and clears this
# probability threshold.
MIN_DSR_PROBABILITY = 0.95


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
    evaluation_mode: str = EVALUATION_MODE_CHAMPION_REPLACEMENT,
    thresholds: ExperimentGateThresholds = DEFAULT_EXPERIMENT_GATE_THRESHOLDS,
    portfolio_thresholds: PortfolioContributionGateThresholds = (
        DEFAULT_PORTFOLIO_CONTRIBUTION_GATE_THRESHOLDS
    ),
    check_materiality: bool = True,
) -> dict[str, Any]:
    """Evaluate either champion replacement or portfolio contribution.

    ``champion_replacement`` remains the default and preserves the historical
    Gate-4 behavior: ``evaluate_experiment_promotion_gate`` (EV/PnL, window
    robustness, drawdown-worse guard, single-ticker/top-5/HHI concentration)
    plus the scout materiality floor.

    ``portfolio_contribution`` is a separate, capital-neutral gate for a small
    sleeve.  It deliberately skips the champion scout-materiality rule and
    delegates to :func:`evaluate_portfolio_contribution_gate`, whose verdict
    can be reject, forward-watch, or accepted default-off portfolio paper.
    """
    if evaluation_mode not in VALID_EVALUATION_MODES:
        raise ValueError(
            f"unsupported evaluation_mode {evaluation_mode!r}; expected one of "
            f"{sorted(VALID_EVALUATION_MODES)}"
        )

    if evaluation_mode == EVALUATION_MODE_PORTFOLIO_CONTRIBUTION:
        portfolio_gate = evaluate_portfolio_contribution_gate(
            window_metrics,
            thresholds=portfolio_thresholds,
        )
        return {
            **portfolio_gate,
            "evaluation_mode": evaluation_mode,
            "portfolio_contribution_gate": portfolio_gate,
            "promotion_gate": None,
            "materiality": None,
            "warnings": list(portfolio_gate.get("warnings", [])),
        }

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
        "evaluation_mode": evaluation_mode,
        "hard_failures": failures,
        "warnings": warnings,
        "promotion_gate": promo,
        "materiality": materiality,
    }


def evaluate_dsr_live_gate(
    dsr_report: dict[str, Any] | None,
) -> dict[str, Any]:
    """Recompute and validate DSR evidence needed for Gate-5 live promotion.

    The three failure classes are intentionally stable for downstream reports:
    missing report, incomplete/untrusted report, and a complete report whose
    probability is below the live threshold. A five-field summary is never
    trusted: the full CLI report must retain ``panel_input`` and Gate 5 reruns
    the formula, panel hash, scope, and probability before using it.
    """
    base = {
        "passed": False,
        "required_probability": MIN_DSR_PROBABILITY,
        "status": None,
        "selection_pool_complete": False,
        "panel_hash": None,
        "selection_scope_id": None,
        "dsr_probability": None,
        "incomplete_fields": [],
        "panel_recomputed": False,
        "recomputation_reason_codes": [],
    }
    if dsr_report is None:
        return {**base, "reason": "dsr_report_missing"}

    if not isinstance(dsr_report, dict):
        return {
            **base,
            "reason": "dsr_report_incomplete",
            "incomplete_fields": ["report_not_object"],
        }

    incomplete_fields: list[str] = []
    panel_input = dsr_report.get("panel_input")
    claimed_panel_result = dsr_report.get("panel_result")
    claimed = dsr_report.get("gate5_dsr_report")
    if not isinstance(panel_input, dict):
        incomplete_fields.append("panel_input")
    if not isinstance(claimed_panel_result, dict):
        incomplete_fields.append("panel_result")
    if not isinstance(claimed, dict):
        incomplete_fields.append("gate5_dsr_report")

    if incomplete_fields:
        return {
            **base,
            "reason": "dsr_report_incomplete",
            "incomplete_fields": incomplete_fields,
        }

    try:
        try:
            from quant.sharpe_inference import evaluate_deflated_sharpe_trial_panel
        except ImportError:
            from sharpe_inference import evaluate_deflated_sharpe_trial_panel

        recomputed = evaluate_deflated_sharpe_trial_panel(
            panel_input.get("trials"),
            selected_config_id=panel_input.get("selected_config_id"),
            expected_attempt_count=panel_input.get("expected_attempt_count"),
            selection_pool_complete=panel_input.get("selection_pool_complete"),
            expected_return_dates=panel_input.get("expected_return_dates"),
            periods_per_year=panel_input.get("periods_per_year", 252),
        )
    except Exception as exc:
        return {
            **base,
            "reason": "dsr_report_incomplete",
            "incomplete_fields": ["panel_recomputation_exception"],
            "recomputation_reason_codes": [type(exc).__name__],
        }

    if recomputed.get("status") != "computable":
        return {
            **base,
            "reason": "dsr_report_incomplete",
            "incomplete_fields": ["panel_recomputation"],
            "panel_recomputed": True,
            "recomputation_reason_codes": list(
                recomputed.get("reason_codes") or ["panel_not_computable"]
            ),
        }

    recomputed_dsr = recomputed.get("dsr") or {}
    context = recomputed.get("context") or {}
    panel_hash = recomputed.get("panel_sha256")
    selection_scope_raw = context.get("selection_scope")
    selection_scope_id = (
        selection_scope_raw.strip()
        if isinstance(selection_scope_raw, str) and selection_scope_raw.strip()
        else None
    )
    probability_raw = recomputed_dsr.get("probability")
    probability = (
        float(probability_raw)
        if isinstance(probability_raw, (int, float))
        and not isinstance(probability_raw, bool)
        and math.isfinite(float(probability_raw))
        else None
    )
    selection_pool_complete = recomputed.get("selection_pool_complete") is True

    claimed_status = claimed.get("status")
    claimed_status = (
        claimed_status.strip().lower() if isinstance(claimed_status, str) else None
    )
    claimed_probability = claimed.get("dsr_probability")
    claimed_probability = (
        float(claimed_probability)
        if isinstance(claimed_probability, (int, float))
        and not isinstance(claimed_probability, bool)
        and math.isfinite(float(claimed_probability))
        else None
    )

    if claimed_status != "computed":
        incomplete_fields.append("status")
    if dsr_report.get("status") != "computable":
        incomplete_fields.append("report_status")
    if claimed_panel_result.get("status") != "computable":
        incomplete_fields.append("panel_result_status")
    if claimed.get("selection_pool_complete") is not True:
        incomplete_fields.append("selection_pool_complete")
    if claimed.get("panel_hash") != panel_hash:
        incomplete_fields.append("panel_hash_recomputation_mismatch")
    if claimed.get("selection_scope_id") != selection_scope_id:
        incomplete_fields.append("selection_scope_recomputation_mismatch")
    if claimed_panel_result.get("panel_sha256") != panel_hash:
        incomplete_fields.append("panel_result_hash_recomputation_mismatch")
    claimed_panel_context = claimed_panel_result.get("context") or {}
    if claimed_panel_context.get("selection_scope") != selection_scope_id:
        incomplete_fields.append("panel_result_scope_recomputation_mismatch")
    claimed_panel_dsr = claimed_panel_result.get("dsr") or {}
    claimed_panel_probability = claimed_panel_dsr.get("probability")
    if (
        not isinstance(claimed_panel_probability, (int, float))
        or isinstance(claimed_panel_probability, bool)
        or probability is None
        or not math.isfinite(float(claimed_panel_probability))
        or not math.isclose(
            float(claimed_panel_probability), probability, rel_tol=0.0, abs_tol=1e-15
        )
    ):
        incomplete_fields.append("panel_result_probability_recomputation_mismatch")
    if probability is None or not 0.0 <= probability <= 1.0:
        incomplete_fields.append("recomputed_dsr_probability")
    if (
        claimed_probability is None
        or probability is None
        or not math.isclose(claimed_probability, probability, rel_tol=0.0, abs_tol=1e-15)
    ):
        incomplete_fields.append("dsr_probability_recomputation_mismatch")

    result = {
        **base,
        "status": claimed_status,
        "selection_pool_complete": selection_pool_complete,
        "panel_hash": panel_hash,
        "selection_scope_id": selection_scope_id,
        "dsr_probability": probability,
        "incomplete_fields": incomplete_fields,
        "panel_recomputed": True,
        "recomputation_reason_codes": [],
    }
    if incomplete_fields:
        return {**result, "reason": "dsr_report_incomplete"}
    if probability < MIN_DSR_PROBABILITY:
        return {**result, "reason": "dsr_probability_below_threshold"}
    return {**result, "passed": True, "reason": None}


def evaluate_live_readiness(
    *,
    envelope: ExecutionEnvelope | None,
    closed_forward_trades: int | None = None,
    forward_pnl: float | None = None,
    replacement_value_passed: bool | None = None,
    kill_switch_parity_passed: bool | None = None,
    dsr_report: dict[str, Any] | None = None,
    min_closed_forward_trades: int = MIN_CLOSED_FORWARD_TRADES,
) -> dict[str, Any]:
    """Codified Gate 5 (AGENTS.md paper-sleeve activation prerequisites).

    A sleeve is live-ready only when all hold:
      - >= ``min_closed_forward_trades`` closed forward 10-day paper trades,
      - positive forward paper PnL,
      - replacement value vs core / cash passed,
      - the execution envelope is complete, and
      - the kill switch + sleeve drawdown stop passed parity tests, and
      - a computed, selection-complete DSR report with stable panel/scope
        identity and ``dsr_probability >= 0.95``.

    ``dsr_report`` is the full output from ``scripts/deflated_sharpe.py``, not
    its nested five-field summary. It remains optional at the API boundary for
    compatibility with old callers. Omitting it, passing a summary alone, or
    altering the claimed hash/probability is fail-closed for live readiness;
    paper/default-off eligibility is unchanged.

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

    dsr_gate = evaluate_dsr_live_gate(dsr_report)
    if not dsr_gate["passed"]:
        blockers.append(dsr_gate["reason"])

    return {
        "ready": not blockers,
        "blockers": blockers,
        "closed_forward_trades": n,
        "min_closed_forward_trades": min_closed_forward_trades,
        "forward_pnl": forward_pnl,
        "replacement_value_passed": bool(replacement_value_passed),
        "kill_switch_parity_passed": bool(kill_switch_parity_passed),
        "envelope_missing": envelope_missing,
        "dsr_gate": dsr_gate,
    }


def _next_step(verdict: str, live_readiness: dict[str, Any]) -> str:
    if verdict == "portfolio_reject":
        return (
            "Reject the portfolio sleeve under the capital-conserving "
            "contribution gate. Do not route it to live or retune it on the "
            "frozen panel."
        )
    if verdict == "portfolio_forward_watch":
        return (
            "Keep the sleeve default-off on the portfolio forward watchlist. "
            "No hard economic or risk failure was established, but required "
            "measurement or trial-adjusted evidence is incomplete; it is "
            "neither accepted paper nor live-eligible."
        )
    if verdict == "accepted_portfolio_paper":
        return (
            "Accept only as a default-off portfolio paper sleeve. This "
            "portfolio-contribution verdict never grants live eligibility; "
            "live promotion requires a separate, explicitly authorized "
            "forward activation contract."
        )
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
        "to reach live -- only resolve the remaining Gate-5 evidence items: "
        f"{remaining}."
    )


def full_stack_verdict(
    *,
    gate4: dict[str, Any],
    live_readiness: dict[str, Any],
    envelope: ExecutionEnvelope | None = None,
    evaluation_mode: str | None = None,
) -> dict[str, Any]:
    """Combine Gate 4 + Gate-5 live-readiness into the selected verdict ladder.

    Champion replacement (the default) preserves the existing ladder:
    ``reject`` -> ``accepted_paper_pending_forward`` -> ``live_eligible``.

    Portfolio contribution maps the delegated gate's fixed verdict directly:
    ``portfolio_reject`` -> ``portfolio_forward_watch`` ->
    ``accepted_portfolio_paper``.  It ignores Gate-5 live readiness and can
    never return ``live_eligible``.  When the caller omits ``evaluation_mode``,
    the mode is inherited from the gate report so a portfolio result cannot be
    accidentally interpreted by the champion/live ladder.
    """
    gate_mode = gate4.get("evaluation_mode")
    if gate_mode is not None and gate_mode not in VALID_EVALUATION_MODES:
        raise ValueError(
            f"unsupported gate4 evaluation_mode {gate_mode!r}; expected one of "
            f"{sorted(VALID_EVALUATION_MODES)}"
        )
    if evaluation_mode is None:
        evaluation_mode = gate_mode or EVALUATION_MODE_CHAMPION_REPLACEMENT
    elif gate_mode is not None and gate_mode != evaluation_mode:
        raise ValueError(
            "evaluation_mode conflicts with gate4 evaluation_mode: "
            f"{evaluation_mode!r} != {gate_mode!r}"
        )
    if evaluation_mode not in VALID_EVALUATION_MODES:
        raise ValueError(
            f"unsupported evaluation_mode {evaluation_mode!r}; expected one of "
            f"{sorted(VALID_EVALUATION_MODES)}"
        )

    if evaluation_mode == EVALUATION_MODE_PORTFOLIO_CONTRIBUTION:
        reported_portfolio_verdict = gate4.get("portfolio_verdict")
        hard_failures = list(gate4.get("hard_failures") or [])
        evidence_blockers = list(gate4.get("evidence_blockers") or [])
        report_consistent = (
            (
                reported_portfolio_verdict == "portfolio_reject"
                and not gate4.get("passed")
                and bool(hard_failures)
            )
            or (
                reported_portfolio_verdict == "portfolio_forward_watch"
                and not gate4.get("passed")
                and not hard_failures
                and bool(evidence_blockers)
            )
            or (
                reported_portfolio_verdict == "accepted_portfolio_paper"
                and gate4.get("passed") is True
                and not hard_failures
                and not evidence_blockers
            )
        )
        if reported_portfolio_verdict not in {
            "portfolio_reject",
            "portfolio_forward_watch",
            "accepted_portfolio_paper",
        } or not report_consistent:
            # Fail closed if a caller supplies a hand-built, stale, or
            # internally contradictory portfolio report.  A string verdict
            # alone must never unlock paper acceptance or the live ladder.
            portfolio_verdict = "portfolio_reject"
            report_consistent = False
        else:
            portfolio_verdict = reported_portfolio_verdict
        verdict = portfolio_verdict
        live_ready = False
    else:
        if not gate4.get("passed"):
            verdict = "reject"
        elif live_readiness.get("ready"):
            verdict = "live_eligible"
        else:
            verdict = "accepted_paper_pending_forward"
        live_ready = bool(live_readiness.get("ready"))

    return {
        "anti_js": "No JavaScript was used.",
        "verdict": verdict,
        "evaluation_mode": evaluation_mode,
        "gate_report_consistent": (
            report_consistent
            if evaluation_mode == EVALUATION_MODE_PORTFOLIO_CONTRIBUTION
            else True
        ),
        "gate4_passed": bool(gate4.get("passed")),
        "live_ready": live_ready,
        "next_step": _next_step(verdict, live_readiness),
        "gate4": gate4,
        "live_readiness": live_readiness,
        "execution_envelope": envelope.to_dict() if envelope is not None else None,
    }
