"""exp-20260520-008: SEC positive-language low-reaction notional.

Alpha search on one production-visible SEC paper-sleeve field interaction.
The broad positive-language scalar failed, but positive filing language with
muted issuer-specific T+1 reaction may represent underreaction rather than
poor quality.  This run tests only a bounded paper-notional scalar for covered
``positive_language`` rows with ``t1_excess_return_vs_spy <= 0.02``.

Core entries, exits, queue eligibility, queue capacity, hold days, LLM, news,
and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

import exp_20260519_012_sec_negative_reaction_absorption_notional as scout


EXPERIMENT_ID = "exp-20260520-008"
STEM = "exp_20260520_008_sec_positive_language_low_reaction_notional"
TARGET_T1_EXCESS_MAX = 0.02

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
    / f"{EXPERIMENT_ID}_sec_positive_language_low_reaction_notional.md"
)
scout.TARGET_SCALAR_VARIANTS = OrderedDict(
    [
        ("negative_reaction_scalar_0_00", 0.00),
        ("negative_reaction_scalar_0_50", 0.50),
        ("negative_reaction_scalar_0_75", 0.75),
        ("negative_reaction_scalar_1_00", 1.00),
        ("negative_reaction_scalar_1_05", 1.05),
        ("negative_reaction_scalar_1_10", 1.10),
        ("negative_reaction_scalar_1_15", 1.15),
        ("negative_reaction_scalar_1_25", 1.25),
        ("negative_reaction_scalar_1_50", 1.50),
    ]
)
ORIGINAL_BUILD_PAYLOAD = scout.build_payload


def _is_positive_low_reaction_candidate(candidate: dict[str, Any]) -> bool:
    t1_excess = scout._float(candidate.get("t1_excess_return_vs_spy"))
    return (
        str(candidate.get("sec_text_coverage_status") or "") == "covered"
        and str(candidate.get("language_bucket") or "") == "positive_language"
        and t1_excess is not None
        and t1_excess <= TARGET_T1_EXCESS_MAX
    )


def _is_positive_low_reaction_position(position: dict[str, Any]) -> bool:
    return _is_positive_low_reaction_candidate(scout._source_candidate(position))


def _notional_for_position(
    position: dict[str, Any],
    *,
    target_scalar: float,
) -> tuple[float, float, str]:
    del target_scalar
    notional, scalar, rule = scout.BASE_NOTIONAL_FOR_POSITION(
        position,
        target_scalar=scout.ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR,
    )
    del notional
    rule_parts = [rule]
    if _is_positive_low_reaction_position(position):
        scalar *= float(scout._ACTIVE_TARGET_SCALAR)
        rule_parts.append("positive_language_low_reaction_scalar")
    return (
        float(scout.parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar,
        scalar,
        "+".join(rule_parts),
    )


def _target_coverage_summary(exp100: dict[str, Any]) -> dict[str, Any]:
    aggregate = {"target": 0, "non_target": 0, "missing_t1_excess": 0}
    by_window: dict[str, Any] = {}
    for label, window in exp100.get("windows", {}).items():
        rows = window.get("candidate_rows") or []
        target = 0
        missing = 0
        for row in rows:
            if (
                str(row.get("sec_text_coverage_status") or "") == "covered"
                and str(row.get("language_bucket") or "") == "positive_language"
                and scout._float(row.get("t1_excess_return_vs_spy")) is None
            ):
                missing += 1
            if _is_positive_low_reaction_candidate(row):
                target += 1
        by_window[label] = {
            "candidate_count": len(rows),
            "target_count": target,
            "positive_language_missing_t1_excess": missing,
        }
        aggregate["target"] += target
        aggregate["missing_t1_excess"] += missing
        aggregate["non_target"] += max(len(rows) - target, 0)
    return {
        "aggregate": aggregate,
        "by_window": by_window,
        "target_definition": {
            "sec_text_coverage_status": "covered",
            "language_bucket": "positive_language",
            "t1_excess_return_vs_spy_lte": TARGET_T1_EXCESS_MAX,
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["gate"]["aggregate_delta"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Positive-Language Low-Reaction Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Best Variant",
        "",
        f"- best_variant: `{payload['best_variant']}`",
        f"- target_scalar: `{payload['parameters']['best_target_scalar']}`",
        f"- EV delta: `{aggregate.get('expected_value_score_sum_delta')}`",
        f"- PnL delta: `${aggregate.get('total_pnl_sum_delta')}`",
        f"- gate_passed: `{payload['gate']['passed']}`",
        "",
        "## Three-Window Deltas",
        "",
        "| Window | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|",
    ]
    for label, row in payload["gate"]["by_window"].items():
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
            json.dumps(scout._safe(payload["gate"]), indent=2, sort_keys=True),
            "```",
            "",
            "## Selection",
            "",
            "```json",
            json.dumps(scout._safe(payload["selection"]), indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


scout._is_negative_reaction_candidate = _is_positive_low_reaction_candidate
scout._is_negative_reaction_position = _is_positive_low_reaction_position
scout._notional_for_position = _notional_for_position
scout._target_coverage_summary = _target_coverage_summary
scout._artifact_markdown = _artifact_markdown


def _repo_rel(path: Path | str) -> str:
    return scout._repo_rel(path)


def _positive_low_reaction_variant_name(name: str) -> str:
    return name.replace("negative_reaction_scalar", "positive_low_reaction_scalar")


def _rename_positive_low_reaction_fields(payload: dict[str, Any]) -> None:
    payload["best_variant"] = _positive_low_reaction_variant_name(payload["best_variant"])
    variants = payload["parameters"].get("target_scalar_variants", {})
    payload["parameters"]["target_scalar_variants"] = {
        _positive_low_reaction_variant_name(name): value
        for name, value in variants.items()
    }
    summaries = payload.get("variant_summaries", {})
    payload["variant_summaries"] = {
        _positive_low_reaction_variant_name(name): row
        for name, row in summaries.items()
    }
    for row in payload["variant_summaries"].values():
        scalar = row.pop("negative_reaction_absorption_notional_scalar", None)
        row["positive_language_low_reaction_notional_scalar"] = scalar


def build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    _rename_positive_low_reaction_fields(payload)
    passed = bool(payload["gate"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "decision": (
                "promising_sec_positive_language_low_reaction_notional"
                if passed
                else "rejected_sec_positive_language_low_reaction_notional"
            ),
            "hypothesis": (
                "Within the SEC financial-report default-off paper sleeve, covered "
                "positive_language rows with muted T+1 excess reaction may be "
                "underreaction candidates. A bounded paper-notional scalar may "
                "improve allocation without changing queue eligibility, hold days, "
                "capacity, or live orders."
            ),
            "change_summary": (
                "Sweep a paper-notional scalar for covered positive_language SEC "
                "rows with t1_excess_return_vs_spy <= 0.02."
            ),
            "change_type": "alpha_search_semantic_reaction_notional_allocation",
            "component": "quant/sec_financial_report_event_sleeve.py",
            "changed_variable": (
                "sec_positive_language_low_reaction_notional_scalar"
            ),
            "single_causal_variable": (
                "positive-language plus T+1 excess <= 2% paper-notional scalar"
            ),
            "interpretation": (
                "Positive-language SEC rows with muted T+1 excess reaction cleared "
                "the paper-sleeve scout gate as an allocation candidate. Promotion "
                "requires moving the same rule into shared default-off SEC paper "
                "sleeve code with parity tests."
                if passed
                else "No positive-language low-reaction scalar cleared the "
                "three-window, tail-aware paper-sleeve gate on top of the latest "
                "accepted SEC stack."
            ),
            "rejection_reason": None
            if passed
            else (
                "No positive-language low-reaction scalar cleared the "
                "three-window, tail-aware paper-sleeve gate."
            ),
            "next_evidence_needed": (
                "Implement only in shared default-off SEC paper sleeve code with "
                "production report visibility and parity tests; keep live orders "
                "disabled until forward replacement-value evidence matures."
                if passed
                else "Do not retry nearby positive-language/reaction scalars on "
                "the frozen sample without a new semantic field or forward evidence."
            ),
            "why_not_other_changes": (
                "State-surface scalar/profile mining is under strict anti-repeat; "
                "broad-market direct pool expansion failed in exp-20260520-007; "
                "LLM soft-ranking lacks replay-safe attribution; broad "
                "positive_language and generic earnings-release scalars already "
                "need added context."
            ),
            "protocol_answers": {
                "1_alpha_hypothesis": (
                    "capital allocation: scale SEC paper rows only when "
                    "language_bucket=positive_language and "
                    "t1_excess_return_vs_spy <= 0.02. This matches the playbook "
                    "priority for SEC semantic expansion with a reaction context "
                    "field."
                ),
                "2_history_check": (
                    "exp-20260518-012 rejected broad positive-language notional; "
                    "exp-20260518-014 accepted neutral underreaction with the "
                    "same T+1 excess boundary; exp-20260519-012/013 rejected "
                    "negative-language reaction branches; exp-20260519-032 "
                    "rejected earnings-release T+1 strength. This run tests the "
                    "missing positive-language underreaction branch."
                ),
                "3_single_causal_variable": (
                    "sec_positive_language_low_reaction_notional_scalar"
                ),
                "4_acceptance_standard": payload["gate"]["rules"],
                "5_reproducibility": (
                    f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
                ),
            },
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": False,
                "parity_test_added": False,
                "default_off_paper_only": True,
                "alters_orders": False,
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "live_default_orders_changed": False,
                "promotion_requirement": (
                    "Positive result must be implemented in shared "
                    "sec_financial_report_event_sleeve.py before it changes any "
                    "production-visible paper report."
                ),
            },
            "related_files": [
                f"quant/experiments/{STEM}.py",
                _repo_rel(scout.OUT_JSON),
                _repo_rel(scout.DOC_LOG),
                _repo_rel(scout.DOC_TICKET),
                _repo_rel(scout.DOC_ARTIFACT),
                _repo_rel(scout.EXPERIMENT_LOG_JSONL),
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"]["target_t1_excess_max"] = TARGET_T1_EXCESS_MAX
    payload["parameters"]["target_t1_excess_lte"] = TARGET_T1_EXCESS_MAX
    return payload


scout.build_payload = build_payload


def main() -> int:
    return scout.main()


if __name__ == "__main__":
    raise SystemExit(main())
