"""exp-20260520-011: SEC neutral earnings moderate-reaction notional.

Alpha search on one production-visible SEC paper-sleeve semantic/reaction
bucket. This tests only covered ``earnings_release_text`` rows with
``neutral_or_mixed_language`` and moderate, not euphoric, T+1 excess reaction:
``0.02 < t1_excess_return_vs_spy <= 0.04``.

The experiment keeps core entries, exits, queue eligibility, queue capacity,
hold days, LLM, news, and live/default orders unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

import exp_20260519_012_sec_negative_reaction_absorption_notional as scout


EXPERIMENT_ID = "exp-20260520-011"
STEM = "exp_20260520_011_sec_neutral_earnings_moderate_reaction_notional"
TARGET_T1_EXCESS_MIN = 0.02
TARGET_T1_EXCESS_MAX = 0.04
TARGET_LANGUAGE_BUCKET = "neutral_or_mixed_language"
TARGET_TEXT_EVENT_TYPE = "earnings_release_text"

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
    / f"{EXPERIMENT_ID}_sec_neutral_earnings_moderate_reaction_notional.md"
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


def _is_target_candidate(candidate: dict[str, Any]) -> bool:
    t1_excess = scout._float(candidate.get("t1_excess_return_vs_spy"))
    return (
        str(candidate.get("sec_text_coverage_status") or "") == "covered"
        and str(candidate.get("language_bucket") or "") == TARGET_LANGUAGE_BUCKET
        and str(candidate.get("text_event_type") or "") == TARGET_TEXT_EVENT_TYPE
        and t1_excess is not None
        and TARGET_T1_EXCESS_MIN < t1_excess <= TARGET_T1_EXCESS_MAX
    )


def _is_target_position(position: dict[str, Any]) -> bool:
    return _is_target_candidate(scout._source_candidate(position))


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
    if _is_target_position(position):
        scalar *= float(scout._ACTIVE_TARGET_SCALAR)
        rule_parts.append("neutral_earnings_moderate_reaction_scalar")
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
                and str(row.get("language_bucket") or "") == TARGET_LANGUAGE_BUCKET
                and str(row.get("text_event_type") or "") == TARGET_TEXT_EVENT_TYPE
                and scout._float(row.get("t1_excess_return_vs_spy")) is None
            ):
                missing += 1
            if _is_target_candidate(row):
                target += 1
        by_window[label] = {
            "candidate_count": len(rows),
            "target_count": target,
            "missing_t1_excess": missing,
        }
        aggregate["target"] += target
        aggregate["missing_t1_excess"] += missing
        aggregate["non_target"] += max(len(rows) - target, 0)
    return {
        "aggregate": aggregate,
        "by_window": by_window,
        "target_definition": {
            "sec_text_coverage_status": "covered",
            "language_bucket": TARGET_LANGUAGE_BUCKET,
            "text_event_type": TARGET_TEXT_EVENT_TYPE,
            "t1_excess_return_vs_spy_gt": TARGET_T1_EXCESS_MIN,
            "t1_excess_return_vs_spy_lte": TARGET_T1_EXCESS_MAX,
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["gate"]["aggregate_delta"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Neutral Earnings Moderate-Reaction Notional",
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


scout._is_negative_reaction_candidate = _is_target_candidate
scout._is_negative_reaction_position = _is_target_position
scout._notional_for_position = _notional_for_position
scout._target_coverage_summary = _target_coverage_summary
scout._artifact_markdown = _artifact_markdown


def _repo_rel(path: Path | str) -> str:
    return scout._repo_rel(path)


def _rename_variant_fields(payload: dict[str, Any]) -> None:
    payload["best_variant"] = payload["best_variant"].replace(
        "negative_reaction_scalar",
        "moderate_reaction_scalar",
    )
    variants = payload["parameters"].get("target_scalar_variants", {})
    payload["parameters"]["target_scalar_variants"] = {
        name.replace("negative_reaction_scalar", "moderate_reaction_scalar"): value
        for name, value in variants.items()
    }
    summaries = payload.get("variant_summaries", {})
    payload["variant_summaries"] = {
        name.replace("negative_reaction_scalar", "moderate_reaction_scalar"): row
        for name, row in summaries.items()
    }
    for row in payload.get("variant_summaries", {}).values():
        scalar = row.pop("negative_reaction_absorption_notional_scalar", None)
        row["neutral_earnings_moderate_reaction_notional_scalar"] = scalar


def build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    _rename_variant_fields(payload)
    passed = bool(payload["gate"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "decision": (
                "promising_sec_neutral_earnings_moderate_reaction_notional"
                if passed
                else "rejected_sec_neutral_earnings_moderate_reaction_notional"
            ),
            "hypothesis": (
                "Within the SEC financial-report default-off paper sleeve, "
                "covered earnings_release_text rows with neutral_or_mixed_language "
                "and moderate T+1 excess reaction may represent confirmed but "
                "not overextended post-earnings drift. A bounded paper-notional "
                "scalar may improve allocation without changing queue eligibility, "
                "hold days, capacity, or live orders."
            ),
            "change_summary": (
                "Sweep a paper-notional scalar for covered neutral/mixed SEC "
                "earnings-release rows with 0.02 < t1_excess_return_vs_spy <= 0.04."
            ),
            "change_type": "alpha_search_semantic_reaction_notional_allocation",
            "component": "quant/sec_financial_report_event_sleeve.py",
            "changed_variable": (
                "sec_neutral_earnings_moderate_reaction_notional_scalar"
            ),
            "single_causal_variable": (
                "neutral/mixed earnings-release plus 2%-4% T+1 excess "
                "paper-notional scalar"
            ),
            "interpretation": (
                "Neutral/mixed SEC earnings-release rows with moderate T+1 excess "
                "reaction cleared the paper-sleeve scout gate as an allocation "
                "candidate. Promotion requires moving the same rule into shared "
                "default-off SEC paper sleeve code with parity tests."
                if passed
                else "No neutral/mixed earnings-release moderate-reaction scalar "
                "cleared the three-window, tail-aware paper-sleeve gate on top "
                "of the latest accepted SEC stack."
            ),
            "rejection_reason": None
            if passed
            else (
                "No neutral/mixed earnings-release moderate-reaction scalar cleared "
                "the three-window, tail-aware paper-sleeve gate."
            ),
            "next_evidence_needed": (
                "Implement only in shared default-off SEC paper sleeve code with "
                "production report visibility and parity tests; keep live orders "
                "disabled until forward replacement-value evidence matures."
                if passed
                else "Do not retry nearby SEC earnings-release moderate-reaction "
                "scalars on the frozen sample without a new semantic field or "
                "forward evidence."
            ),
            "why_not_other_changes": (
                "State-surface scalar/profile mining is under strict anti-repeat; "
                "broad-market nearby support scalars just produced a rejection; "
                "LLM soft-ranking lacks replay-safe attribution; the latest SEC "
                "underreaction and positive-language branches failed tail/sample "
                "guards, so this tests a distinct neutral moderate-reaction bucket."
            ),
            "protocol_answers": {
                "1_alpha_hypothesis": (
                    "capital allocation: scale SEC paper rows only when "
                    "text_event_type=earnings_release_text, "
                    "language_bucket=neutral_or_mixed_language, and "
                    "0.02 < t1_excess_return_vs_spy <= 0.04. This matches the "
                    "playbook priority for SEC semantic expansion with event and "
                    "reaction context fields."
                ),
                "2_history_check": (
                    "exp-20260518-014 accepted neutral underreaction with market "
                    "context; exp-20260519-008 accepted earnings-release SPY "
                    "context; exp-20260519-032 rejected broad earnings-release "
                    "T+1 strength; exp-20260520-010 rejected the neutral/mixed "
                    "underreaction intersection due to tail concentration. This "
                    "run tests only the neutral/mixed 2%-4% moderate-reaction "
                    "bucket."
                ),
                "3_single_causal_variable": (
                    "sec_neutral_earnings_moderate_reaction_notional_scalar"
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
    payload["parameters"]["target_language_bucket"] = TARGET_LANGUAGE_BUCKET
    payload["parameters"]["target_text_event_type"] = TARGET_TEXT_EVENT_TYPE
    payload["parameters"]["target_t1_excess_min"] = TARGET_T1_EXCESS_MIN
    payload["parameters"]["target_t1_excess_max"] = TARGET_T1_EXCESS_MAX
    return payload


scout.build_payload = build_payload


def main() -> int:
    return scout.main()


if __name__ == "__main__":
    raise SystemExit(main())
