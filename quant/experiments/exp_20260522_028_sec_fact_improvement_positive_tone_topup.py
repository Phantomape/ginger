"""exp-20260522-028: SEC fact-improvement positive-tone top-up scout.

Alpha search on one production-visible, default-off SEC financial-report
paper-sleeve attribution bucket. The field already exists as read-only
attribution in ``sec_financial_report_event_sleeve``; this experiment tests
only whether ``fact_improvement_positive_tone`` deserves a bounded
paper-notional scalar.

No JavaScript is used. Core entries, exits, queue eligibility, LLM/news, and
live/default orders remain unchanged.
"""

from __future__ import annotations

from collections import OrderedDict
import json
from pathlib import Path
from typing import Any

import exp_20260522_011_sec_fact_tone_divergence_haircut as base


EXPERIMENT_ID = "exp-20260522-028"
STEM = "exp_20260522_028_sec_fact_improvement_positive_tone_topup"
TARGET_BUCKET = "fact_improvement_positive_tone"
SCALAR_FIELD = "sec_fact_improvement_positive_tone_notional_scalar"
TRIAL_FAMILY = "sec_fact_tone_gap_semantic_allocation"
BASELINE_SCALAR = 1.0

TARGET_SCALAR_VARIANTS: "OrderedDict[str, float]" = OrderedDict(
    [
        ("negative_reaction_scalar_0_75", 0.75),
        ("negative_reaction_scalar_1_00", 1.00),
        ("negative_reaction_scalar_1_10", 1.10),
        ("negative_reaction_scalar_1_25", 1.25),
        ("negative_reaction_scalar_1_50", 1.50),
    ]
)

STANDARD_WINDOWS: dict[str, dict[str, str]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}

REPO_ROOT = base.scout.REPO_ROOT
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_fact_improvement_positive_tone_topup.md"
)


def _variant_key(name: str) -> str:
    return name.replace("negative_reaction", "fact_improvement_positive_tone")


def _configure_experiment() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TARGET_BUCKET = TARGET_BUCKET
    base.SCALAR_FIELD = SCALAR_FIELD
    base.TARGET_SCALAR_VARIANTS = TARGET_SCALAR_VARIANTS
    base.scout.EXPERIMENT_ID = EXPERIMENT_ID
    base.scout.STEM = STEM
    base.scout.OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
    base.scout.OUT_JSON = OUT_JSON
    base.scout.DOC_LOG = DOC_LOG
    base.scout.DOC_TICKET = DOC_TICKET
    base.scout.DOC_ARTIFACT = DOC_ARTIFACT
    base.scout.TARGET_SCALAR_VARIANTS = TARGET_SCALAR_VARIANTS
    base._variant_key = _variant_key
    base.scout._notional_for_position = _notional_for_position


def _notional_for_position(
    position: dict[str, Any],
    *,
    target_scalar: float = base.scout.ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR,
) -> tuple[float, float, str]:
    _base_notional, scalar, rule = base.scout.BASE_NOTIONAL_FOR_POSITION(
        position,
        target_scalar=base.scout.ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR,
    )
    del _base_notional, target_scalar
    rule_parts = [part for part in rule.split("+") if part]
    if base._is_target_position(position):
        scalar *= base.scout._ACTIVE_TARGET_SCALAR
        rule_parts.append("fact_improvement_positive_tone_scalar")
    return (
        float(base.scout.parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar,
        scalar,
        "+".join(rule_parts) or "default",
    )


def _failed_gate_reasons(gate: dict[str, Any]) -> list[str]:
    checks = gate.get("checks") or {}
    if not isinstance(checks, dict):
        return [str(gate.get("reason") or "gate_failed")]
    return [name for name, passed in checks.items() if not passed]


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    gate = payload.get("gate") or {}
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload.get("timestamp"),
        "status": payload.get("status"),
        "hypothesis": payload.get("hypothesis"),
        "change_summary": payload.get("change_summary"),
        "change_type": "alpha_search",
        "mechanism_family": TRIAL_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "fact_improvement_positive_tone_topup",
        "changed_variable": SCALAR_FIELD,
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260522-011",
            "exp-20260522-022",
            "exp-20260520-015",
            "exp-20260520-012",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "previously_untested_production_visible_fact_tone_bucket",
        "component": "offline_sec_financial_report_paper_sleeve_replay",
        "parameters": payload.get("parameters"),
        "date_range": payload.get("date_range") or STANDARD_WINDOWS,
        "backtest_protocol": payload.get("backtest_protocol"),
        "before_metrics": payload.get("before_metrics"),
        "after_metrics": payload.get("after_metrics"),
        "delta_metrics": payload.get("gate"),
        "expected_value_score_delta": payload.get("expected_value_score_delta"),
        "production_impact": payload.get("production_impact"),
        "decision": payload.get("decision"),
        "rejection_reason": payload.get("rejection_reason"),
        "next_evidence_needed": payload.get("next_evidence_needed"),
        "related_files": payload.get("related_files"),
        "gate4": {
            "passed": gate.get("passed"),
            "failed_checks": _failed_gate_reasons(gate),
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload.get("gate") or {}
    aggregate = gate.get("aggregate_delta") or {}
    lines = [
        f"# {EXPERIMENT_ID} SEC Fact-Improvement Positive-Tone Top-Up",
        "",
        f"Decision: `{payload.get('decision')}`.",
        "",
        "## Hypothesis",
        "",
        str(payload.get("hypothesis") or ""),
        "",
        "## Trial Accounting",
        "",
        f"- trial_family: `{TRIAL_FAMILY}`",
        f"- changed_variable: `{SCALAR_FIELD}`",
        "- prior_trial_count: `3`",
        "- multiple_testing_risk_bucket: `moderate`",
        "- new_evidence_type: `previously_untested_production_visible_fact_tone_bucket`",
        "",
        "## Best Variant",
        "",
        f"- best_variant: `{payload.get('best_variant')}`",
        f"- target_scalar: `{payload.get('parameters', {}).get('best_target_scalar')}`",
        f"- EV delta: `{aggregate.get('expected_value_score_sum_delta')}`",
        f"- PnL delta: `${aggregate.get('total_pnl_sum_delta')}`",
        f"- gate_passed: `{gate.get('passed')}`",
        "",
        "## Three-Window Deltas",
        "",
        "| Window | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|",
    ]
    for label, row in (gate.get("by_window") or {}).items():
        lines.append(
            "| {label} | {ev:+.4f} | ${pnl:+,.2f} | {dd:+.4f} |".format(
                label=label,
                ev=float(row.get("expected_value_score") or 0.0),
                pnl=float(row.get("total_pnl") or 0.0),
                dd=float(row.get("max_drawdown_pct") or 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(base.scout._safe(gate), indent=2, sort_keys=True),
            "```",
            "",
            "## Target Coverage",
            "",
            "```json",
            json.dumps(
                base.scout._safe(payload.get("target_coverage")),
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Production Impact",
            "",
            "No shared policy, production adapter, live/default order path, or LLM boundary changed. This is an offline default-off paper-sleeve scout.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    _configure_experiment()
    payload = base.build_payload()
    gate = payload.get("gate") or {}
    aggregate_delta = gate.get("aggregate_delta") or {}
    gate_passed = bool(gate.get("passed"))
    if gate_passed:
        status = "accepted_candidate"
        decision = "promising_sec_fact_improvement_positive_tone_topup"
        interpretation = (
            "The fact-improvement positive-tone scalar cleared the paper-sleeve "
            "scout gate, but remains offline until moved into shared policy with "
            "parity tests."
        )
        rejection_reason = None
    else:
        status = "rejected"
        decision = "rejected_sec_fact_improvement_positive_tone_topup"
        interpretation = (
            "No fact-improvement positive-tone scalar cleared the three-window, "
            "tail-aware paper-sleeve gate on top of the accepted SEC stack."
        )
        rejection_reason = gate.get("reason") or interpretation

    best_variant = str(
        payload.get("best_variant") or "fact_improvement_positive_tone_scalar_1_00"
    )
    best_summary = (payload.get("variant_summaries") or {}).get(best_variant, {})
    best_scalar = best_summary.get(SCALAR_FIELD)
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "stem": STEM,
            "status": status,
            "decision": decision,
            "lane": "alpha_search",
            "hypothesis": (
                "SEC financial-report T+1 rows with explicit improving facts and "
                "positive tone may have better replacement value than generic "
                "financial-report drift rows. A bounded paper-notional scalar tests "
                "that semantic quality bucket without changing eligibility, exits, "
                "live orders, or LLM authority."
            ),
            "change_summary": (
                "Sweep a bounded paper-notional scalar for "
                "fact_tone_gap_bucket=fact_improvement_positive_tone."
            ),
            "change_type": "alpha_search",
            "component": "offline_sec_financial_report_paper_sleeve_replay",
            "changed_variable": SCALAR_FIELD,
            "single_causal_variable": SCALAR_FIELD,
            "trial_family": TRIAL_FAMILY,
            "trial_accounting": {
                "trial_family": TRIAL_FAMILY,
                "changed_variable": SCALAR_FIELD,
                "prior_trial_count": 3,
                "nearby_prior_experiments": [
                    "exp-20260522-011",
                    "exp-20260522-022",
                    "exp-20260520-015",
                    "exp-20260520-012",
                ],
                "multiple_testing_risk_bucket": "moderate",
                "new_evidence_type": (
                    "previously_untested_production_visible_fact_tone_bucket"
                ),
            },
            "parameters": {
                "baseline_target_scalar": BASELINE_SCALAR,
                "target_scalar_variants": {
                    _variant_key(name): scalar
                    for name, scalar in TARGET_SCALAR_VARIANTS.items()
                },
                "best_target_scalar": best_scalar,
                "target_bucket": TARGET_BUCKET,
                "fact_tone_gap_rule_version": "sec_fact_tone_gap_bucket_v1",
                "accepted_earnings_release_spy_context_scalar": (
                    base.scout.ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR
                ),
                "base_event_notional_usd": float(base.scout.parent.DEFAULT_EVENT_NOTIONAL_USD),
                "max_positions": base.scout.parent.DEFAULT_MAX_POSITIONS,
                "anti_js": "No JavaScript was used.",
            },
            "target_definition": {
                "field": "fact_tone_gap_bucket",
                "target_bucket": TARGET_BUCKET,
                "source": "build_fact_tone_gap_attribution(candidate)",
            },
            "expected_value_score_delta": aggregate_delta.get(
                "expected_value_score_sum_delta"
            ),
            "total_pnl_delta": aggregate_delta.get("total_pnl_sum_delta"),
            "interpretation": interpretation,
            "rejection_reason": rejection_reason,
            "next_evidence_needed": (
                "Do not retry nearby fact-improvement positive-tone scalars on the "
                "same frozen sample unless forward SEC rows add enough evidence or "
                "the bucket is paired with a distinct production-visible "
                "replacement-value signal."
            ),
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_paper_only": True,
                "alters_orders": False,
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "live_default_orders_changed": False,
            },
            "llm_metrics": {
                "used_llm": False,
                "llm_role_changed": False,
                "blocker_relation": (
                    "LLM soft-ranking remains attribution-sparse, so this run uses "
                    "a deterministic production-visible SEC text attribution bucket."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking due sparse attribution; skipped "
                "state-surface, broad-market, low-deployment ETF, Space, and event "
                "source/reaction retunes because recent logs show high "
                "multiple-testing risk, sample blockers, or identity/replacement "
                "value gaps."
            ),
            "protocol_answers": {
                "alpha_hypothesis": (
                    "capital allocation: positive factual improvement plus positive "
                    "tone may identify better SEC financial-report continuation quality."
                ),
                "past_nearby_experiments": (
                    "exp-20260522-011 rejected fact-tone divergence haircuts; "
                    "exp-20260522-022 rejected fact-negative/guidance-cut haircuts; "
                    "this tests the previously untested positive-quality bucket."
                ),
                "single_causal_variable": SCALAR_FIELD,
                "acceptance_standard": (
                    "Same three-window protocol as docs/backtesting.md; retain only "
                    "if aggregate EV/PnL improve without unacceptable window, "
                    "drawdown, sample, or concentration failures."
                ),
                "reproducibility": (
                    f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
                ),
            },
        }
    )
    return payload


def persist(payload: dict[str, Any]) -> None:
    base.scout.persist(payload)
    base.scout._upsert_jsonl(base.scout.EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))


def main() -> int:
    payload = build_payload()
    base.scout._artifact_markdown = _artifact_markdown
    persist(payload)
    print(
        json.dumps(
            base.scout._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "best_variant": payload["best_variant"],
                    "aggregate_ev_delta": payload["expected_value_score_delta"],
                    "aggregate_pnl_delta": payload["total_pnl_delta"],
                    "gate_passed": payload["gate"]["passed"],
                    "window_checks": payload["gate"]["by_window"],
                    "selection": payload.get("selection"),
                    "target_coverage": payload.get("target_coverage"),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
