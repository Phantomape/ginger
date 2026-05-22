"""exp-20260522-011: SEC fact-tone divergence notional haircut.

Alpha search on one production-visible, default-off SEC financial-report
paper-sleeve attribution field.  The field already exists in the shared sleeve
as read-only attribution; this experiment tests only whether the fixed
``fact_tone_divergence`` bucket deserves a bounded paper-notional haircut.

Core entries, exits, candidate eligibility, queue capacity, hold days, LLM,
news, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
import json
from typing import Any

import exp_20260519_012_sec_negative_reaction_absorption_notional as scout
from sec_financial_report_event_sleeve import build_fact_tone_gap_attribution


EXPERIMENT_ID = "exp-20260522-011"
STEM = "exp_20260522_011_sec_fact_tone_divergence_haircut"
TARGET_BUCKET = "fact_tone_divergence"
SCALAR_FIELD = "sec_fact_tone_divergence_notional_scalar"
TRIAL_FAMILY = "sec_fact_tone_gap_semantic_allocation"
BASELINE_SCALAR = 1.0

TARGET_SCALAR_VARIANTS: "OrderedDict[str, float]" = OrderedDict(
    [
        ("negative_reaction_scalar_0_00", 0.00),
        ("negative_reaction_scalar_0_25", 0.25),
        ("negative_reaction_scalar_0_50", 0.50),
        ("negative_reaction_scalar_0_75", 0.75),
        ("negative_reaction_scalar_1_00", 1.00),
    ]
)

scout.EXPERIMENT_ID = EXPERIMENT_ID
scout.STEM = STEM
scout.OUT_DIR = scout.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
scout.OUT_JSON = scout.OUT_DIR / f"{STEM}.json"
scout.DOC_LOG = scout.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
scout.DOC_TICKET = scout.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
scout.DOC_ARTIFACT = (
    scout.REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_fact_tone_divergence_haircut.md"
)
scout.TARGET_SCALAR_VARIANTS = TARGET_SCALAR_VARIANTS
scout._ACTIVE_TARGET_SCALAR = BASELINE_SCALAR

ORIGINAL_BUILD_PAYLOAD = scout.build_payload


def _fact_tone_bucket(candidate: dict[str, Any] | None) -> str:
    if not isinstance(candidate, dict):
        return "missing_candidate"
    attribution = candidate.get("fact_tone_gap_attribution")
    if isinstance(attribution, dict) and attribution.get("fact_tone_gap_bucket"):
        return str(attribution["fact_tone_gap_bucket"])
    return str(build_fact_tone_gap_attribution(candidate).get("fact_tone_gap_bucket"))


def _is_target_candidate(candidate: dict[str, Any]) -> bool:
    return _fact_tone_bucket(candidate) == TARGET_BUCKET


def _is_target_position(position: dict[str, Any]) -> bool:
    return _is_target_candidate(scout._source_candidate(position))


def _notional_for_position(
    position: dict[str, Any],
    *,
    target_scalar: float = scout.ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR,
) -> tuple[float, float, str]:
    _base_notional, scalar, rule = scout.BASE_NOTIONAL_FOR_POSITION(
        position,
        target_scalar=scout.ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR,
    )
    rule_parts = [part for part in rule.split("+") if part]
    if _is_target_position(position):
        scalar *= scout._ACTIVE_TARGET_SCALAR
        rule_parts.append("fact_tone_divergence_scalar")
    return (
        float(scout.parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar,
        scalar,
        "+".join(rule_parts) or "default",
    )


def _target_coverage_summary(exp100: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    bucket_counts: Counter[str] = Counter()
    target_tickers: Counter[str] = Counter()
    total_candidates = 0
    target_candidates = 0
    for window_name, window_payload in exp100.get("windows", {}).items():
        rows = window_payload.get("candidate_rows", []) or []
        window_bucket_counts: Counter[str] = Counter()
        window_targets: list[dict[str, Any]] = []
        for row in rows:
            bucket = _fact_tone_bucket(row)
            window_bucket_counts[bucket] += 1
            bucket_counts[bucket] += 1
            if bucket == TARGET_BUCKET:
                window_targets.append(row)
                target_tickers.update([str(row.get("ticker") or "").upper()])
        total_candidates += len(rows)
        target_candidates += len(window_targets)
        by_window[window_name] = {
            "candidate_rows": len(rows),
            "bucket_counts": dict(sorted(window_bucket_counts.items())),
            "target_rows": len(window_targets),
            "target_tickers": sorted(
                {str(row.get("ticker") or "").upper() for row in window_targets}
            ),
            "target_accessions": sorted(
                {
                    str(
                        row.get("accession_number")
                        or row.get("source_accession_number")
                        or row.get("accession")
                        or ""
                    )
                    for row in window_targets
                    if row.get("accession_number")
                    or row.get("source_accession_number")
                    or row.get("accession")
                }
            ),
        }
    return {
        "total_candidate_rows": total_candidates,
        "target_candidate_rows": target_candidates,
        "target_share": (target_candidates / total_candidates) if total_candidates else 0.0,
        "target_bucket": TARGET_BUCKET,
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "by_window": by_window,
        "target_tickers": dict(sorted(target_tickers.items())),
    }


def _variant_key(name: str) -> str:
    return name.replace("negative_reaction", "fact_tone_divergence")


def _rename_variant_fields(payload: dict[str, Any]) -> dict[str, Any]:
    summaries = payload.get("variant_summaries", {}) or {}
    renamed_summaries: dict[str, dict[str, Any]] = {}
    for name, row in summaries.items():
        row = dict(row)
        scalar = row.pop("negative_reaction_absorption_notional_scalar", None)
        row[SCALAR_FIELD] = scalar
        renamed_summaries[_variant_key(name)] = row
    payload["variant_summaries"] = renamed_summaries

    selections = payload.get("selection_summaries", {}) or {}
    payload["selection_summaries"] = {
        _variant_key(name): value for name, value in selections.items()
    }
    payload["window_variants"] = {
        window_name: {
            _variant_key(name): value for name, value in variants.items()
        }
        for window_name, variants in (payload.get("window_variants", {}) or {}).items()
    }
    gate = payload.get("gate") or {}
    if gate.get("selected_variant"):
        gate["selected_variant"] = _variant_key(str(gate["selected_variant"]))
    payload["gate"] = gate
    if payload.get("best_variant"):
        payload["best_variant"] = _variant_key(str(payload["best_variant"]))
    return payload


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    gate = payload.get("gate", {}) or {}
    selected = payload.get("best_variant") or gate.get("selected_variant")
    selected_summary = (payload.get("variant_summaries", {}) or {}).get(
        str(selected),
        {},
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload.get("timestamp"),
        "hypothesis": payload.get("hypothesis"),
        "change_type": "alpha_search",
        "changed_variable": SCALAR_FIELD,
        "trial_accounting": payload.get("trial_accounting"),
        "parameters": payload.get("parameters"),
        "backtest_protocol": payload.get("backtest_protocol"),
        "before_metrics": payload.get("before_metrics"),
        "after_metrics": selected_summary,
        "expected_value_score_delta": payload.get("expected_value_score_delta"),
        "decision": payload.get("decision"),
        "rejection_reason": payload.get("rejection_reason"),
        "next_evidence_needed": payload.get("next_evidence_needed"),
        "production_impact": payload.get("production_impact"),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload.get("gate", {}) or {}
    aggregate = gate.get("aggregate_delta", {}) or {}
    lines = [
        f"# {EXPERIMENT_ID} SEC Fact-Tone Divergence Haircut",
        "",
        f"Decision: `{payload.get('decision')}`.",
        "",
        "## Hypothesis",
        "",
        str(payload.get("hypothesis") or ""),
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
    for label, row in (gate.get("by_window", {}) or {}).items():
        lines.append(
            "| {label} | {ev:+.4f} | ${pnl:+,.2f} | {dd:+.4f} |".format(
                label=label,
                ev=row.get("expected_value_score", 0.0),
                pnl=row.get("total_pnl", 0.0),
                dd=row.get("max_drawdown_pct", 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(scout._safe(gate), indent=2, sort_keys=True),
            "```",
            "",
            "## Target Coverage",
            "",
            "```json",
            json.dumps(
                scout._safe(payload.get("target_coverage")),
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "No JavaScript was used.",
            "",
            "## Production impact",
            "",
            "No shared policy or live adapter changed. This is an offline default-off paper-sleeve scout; promotion would require shared policy wiring and parity tests.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    payload = _rename_variant_fields(payload)
    target_coverage = payload.get("target_coverage_summary", {}) or {}
    gate = payload.get("gate", {}) or {}
    aggregate_delta = gate.get("aggregate_delta", {}) or {}
    gate_passed = bool(gate.get("passed"))
    if gate_passed:
        status = "accepted_candidate"
        decision = "promising_sec_fact_tone_divergence_haircut"
        interpretation = (
            "The fact-tone divergence haircut cleared the paper-sleeve scout gate, "
            "but remains offline until moved into shared policy with parity tests."
        )
        rejection_reason = None
    else:
        status = "rejected"
        decision = "rejected_sec_fact_tone_divergence_haircut"
        interpretation = (
            "No fact-tone divergence haircut cleared the three-window, tail-aware "
            "paper-sleeve gate on top of the accepted SEC stack."
        )
        rejection_reason = gate.get("reason") or interpretation
    best_variant = str(payload.get("best_variant") or "fact_tone_divergence_scalar_1_00")
    best_summary = (payload.get("variant_summaries", {}) or {}).get(best_variant, {})
    best_scalar = best_summary.get(SCALAR_FIELD)
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "stem": STEM,
            "status": status,
            "decision": decision,
            "lane": "alpha_search",
            "hypothesis": (
                "SEC financial-report T+1 rows whose positive and negative factual "
                "language conflict may be lower-replacement-value continuation candidates. "
                "A bounded paper-notional haircut can reduce exposure without changing "
                "eligibility, exits, live orders, or LLM authority."
            ),
            "change_summary": (
                "Sweep a bounded paper-notional haircut for the fixed "
                "fact_tone_gap_bucket=fact_tone_divergence cohort."
            ),
            "change_type": "alpha_search",
            "component": "offline_sec_financial_report_paper_sleeve_replay",
            "changed_variable": SCALAR_FIELD,
            "single_causal_variable": SCALAR_FIELD,
            "trial_family": TRIAL_FAMILY,
            "trial_accounting": {
                "trial_family": TRIAL_FAMILY,
                "changed_variable": SCALAR_FIELD,
                "prior_trial_count": 2,
                "nearby_prior_experiments": [
                    "exp-20260520-029",
                    "exp-20260520-034",
                    "exp-20260517-017",
                    "exp-20260521-021",
                ],
                "multiple_testing_risk_bucket": "moderate",
                "new_evidence_type": "production_visible_fact_tone_gap_bucket_now_backtestable",
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
                    scout.ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR
                ),
                "base_event_notional_usd": float(scout.parent.DEFAULT_EVENT_NOTIONAL_USD),
                "max_positions": scout.parent.DEFAULT_MAX_POSITIONS,
                "anti_js": "No JavaScript was used.",
            },
            "target_definition": {
                "field": "fact_tone_gap_bucket",
                "target_bucket": TARGET_BUCKET,
                "source": "build_fact_tone_gap_attribution(candidate)",
            },
            "target_coverage": target_coverage,
            "expected_value_score_delta": aggregate_delta.get(
                "expected_value_score_sum_delta"
            ),
            "total_pnl_delta": aggregate_delta.get("total_pnl_sum_delta"),
            "interpretation": interpretation,
            "rejection_reason": rejection_reason,
            "next_evidence_needed": (
                "Do not retry nearby fact-tone bucket scalars on the same frozen sample "
                "unless forward SEC rows add enough evidence or the field is paired with "
                "a distinct production-visible replacement-value signal."
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
                    "LLM soft-ranking data remains sparse, so this run uses a deterministic "
                    "production-visible SEC text attribution field instead."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking due sparse attribution; skipped broad-market "
                "because candidate identity remains unstable; skipped state-surface and "
                "event-source scalar retunes because recent logs show high multiple-testing "
                "risk and tighter materiality requirements."
            ),
            "protocol_answers": {
                "alpha_hypothesis": (
                    "capital allocation: fact-tone divergence may identify weaker SEC "
                    "financial-report continuation quality."
                ),
                "past_nearby_experiments": (
                    "exp-20260520-029 created observed fact-tone attribution; "
                    "exp-20260520-034 found it was not yet backtestable then; "
                    "recent no-guidance/operational fact-density scouts failed on separate "
                    "semantic fields."
                ),
                "single_causal_variable": SCALAR_FIELD,
                "acceptance_standard": (
                    "Same three-window protocol as docs/backtesting.md; retain only if "
                    "aggregate EV/PnL improve without unacceptable window, drawdown, sample, "
                    "or concentration failures."
                ),
                "reproducibility": (
                    f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
                ),
            },
        }
    )
    return payload


scout._is_negative_reaction_candidate = _is_target_candidate
scout._is_negative_reaction_position = _is_target_position
scout._notional_for_position = _notional_for_position
scout._target_coverage_summary = _target_coverage_summary
scout._artifact_markdown = _artifact_markdown
scout.build_payload = build_payload


def persist(payload: dict[str, Any]) -> None:
    scout.persist(payload)
    scout._upsert_jsonl(scout.EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))


def main() -> int:
    payload = scout.build_payload()
    persist(payload)
    print(
        json.dumps(
            scout._safe(
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
