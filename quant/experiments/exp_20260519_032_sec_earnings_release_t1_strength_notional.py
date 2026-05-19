"""exp-20260519-032: SEC earnings-release T+1 strength notional.

Alpha search on one production-visible default-off SEC paper-sleeve field
interaction. The accepted earnings-release SPY T+1 context scalar is fixed;
this run tests whether those rows deserve an additional paper-notional scalar
only when the issuer's T+1 excess return versus SPY confirms strong demand.

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


EXPERIMENT_ID = "exp-20260519-032"
STEM = "exp_20260519_032_sec_earnings_release_t1_strength_notional"
TARGET_T1_EXCESS_MIN = 0.03

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
    / f"{EXPERIMENT_ID}_sec_earnings_release_t1_strength_notional.md"
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
    ]
)
ORIGINAL_BUILD_PAYLOAD = scout.build_payload


def _is_t1_strength_candidate(candidate: dict[str, Any]) -> bool:
    t1_excess = scout._float(candidate.get("t1_excess_return_vs_spy"))
    return (
        scout.base._is_target_candidate(candidate)
        and t1_excess is not None
        and t1_excess >= TARGET_T1_EXCESS_MIN
    )


def _is_t1_strength_position(position: dict[str, Any]) -> bool:
    return _is_t1_strength_candidate(scout._source_candidate(position))


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
    if _is_t1_strength_position(position):
        scalar *= float(scout._ACTIVE_TARGET_SCALAR)
        rule_parts.append("earnings_release_text_t1_strength_scalar")
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
            if scout.base._is_target_candidate(row):
                if scout._float(row.get("t1_excess_return_vs_spy")) is None:
                    missing += 1
                if _is_t1_strength_candidate(row):
                    target += 1
        by_window[label] = {
            "candidate_count": len(rows),
            "target_count": target,
            "earnings_release_spy_context_missing_t1_excess": missing,
        }
        aggregate["target"] += target
        aggregate["missing_t1_excess"] += missing
        aggregate["non_target"] += max(len(rows) - target, 0)
    return {
        "aggregate": aggregate,
        "by_window": by_window,
        "target_definition": {
            "text_event_type": scout.base.TARGET_TEXT_EVENT_TYPE,
            "spy_t1_return_min": scout.base.SPY_T1_RETURN_MIN,
            "t1_excess_return_vs_spy_gte": TARGET_T1_EXCESS_MIN,
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["gate"]["aggregate_delta"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Earnings-Release T+1 Strength Notional",
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


scout._is_negative_reaction_candidate = _is_t1_strength_candidate
scout._is_negative_reaction_position = _is_t1_strength_position
scout._notional_for_position = _notional_for_position
scout._target_coverage_summary = _target_coverage_summary
scout._artifact_markdown = _artifact_markdown


def _repo_rel(path: Path | str) -> str:
    return scout._repo_rel(path)


def _strength_variant_name(name: str) -> str:
    return name.replace("negative_reaction_scalar", "t1_strength_scalar")


def _rename_strength_fields(payload: dict[str, Any]) -> None:
    payload["best_variant"] = _strength_variant_name(payload["best_variant"])
    variants = payload["parameters"].get("target_scalar_variants", {})
    payload["parameters"]["target_scalar_variants"] = {
        _strength_variant_name(name): value for name, value in variants.items()
    }
    summaries = payload.get("variant_summaries", {})
    payload["variant_summaries"] = {
        _strength_variant_name(name): row for name, row in summaries.items()
    }
    for row in payload["variant_summaries"].values():
        scalar = row.pop("negative_reaction_absorption_notional_scalar", None)
        row["earnings_release_text_t1_strength_notional_scalar"] = scalar


def build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    _rename_strength_fields(payload)
    passed = bool(payload["gate"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "decision": (
                "promising_sec_earnings_release_t1_strength_notional"
                if passed
                else "rejected_sec_earnings_release_t1_strength_notional"
            ),
            "hypothesis": (
                "Within the accepted SEC earnings-release SPY-context paper "
                "branch, rows with t1_excess_return_vs_spy >= 0.03 may have "
                "stronger post-event continuation; a bounded paper-notional "
                "scalar can improve allocation without changing queue "
                "eligibility, hold days, capacity, or live orders."
            ),
            "change_summary": (
                "Sweep a paper-notional scalar for SEC earnings_release_text rows "
                "that already pass SPY T+1 context and have T+1 excess >= 3%."
            ),
            "change_type": "alpha_search_event_reaction_notional_allocation",
            "component": "quant/sec_financial_report_event_sleeve.py",
            "changed_variable": "sec_earnings_release_text_t1_strength_notional_scalar",
            "single_causal_variable": (
                "earnings-release SPY-context plus T+1 excess >= 3% paper-notional scalar"
            ),
            "interpretation": (
                "Earnings-release rows with strong issuer-specific T+1 excess "
                "cleared the paper-sleeve scout gate as an allocation candidate. "
                "Promotion requires moving the same rule into shared default-off "
                "SEC paper-sleeve code with parity tests."
                if passed
                else "No T+1 strength scalar cleared the three-window, tail-aware "
                "paper-sleeve gate on top of the latest accepted SEC stack."
            ),
            "rejection_reason": None
            if passed
            else (
                "No T+1 strength scalar cleared the canonical three-window, "
                "tail-aware SEC paper-sleeve gate."
            ),
            "next_evidence_needed": (
                "Implement only in shared default-off SEC paper sleeve code with "
                "production report visibility and parity tests; keep live orders "
                "disabled until forward replacement-value evidence matures."
                if passed
                else "Do not retry nearby earnings-release T+1 excess thresholds "
                "on the frozen sample without a new semantic field or forward evidence."
            ),
            "why_not_other_changes": (
                "State-surface absolute-score/queue/rank near-neighbor sweeps are "
                "anti-repeat after exp-20260519-031; broad earnings-release scalars "
                "already failed; LLM soft-ranking remains too sparse for a clean "
                "attribution experiment, so this uses deterministic SEC event fields."
            ),
        }
    )
    payload["status"] = "accepted_candidate" if passed else "rejected"
    payload["parameters"]["target_t1_excess_min"] = TARGET_T1_EXCESS_MIN
    payload["parameters"].pop("target_t1_excess_max", None)
    payload["protocol_answers"]["1_alpha_hypothesis"] = (
        "capital allocation: scale SEC earnings-release paper rows only when "
        "text_event_type=earnings_release_text, spy_t1_return >= -0.005, and "
        "t1_excess_return_vs_spy >= 0.03."
    )
    payload["protocol_answers"]["2_history_check"] = (
        "exp-20260519-007 rejected broad earnings-release text notional; "
        "exp-20260519-008 accepted SPY T+1 context; exp-20260519-010 rejected "
        "overlap-stack cap. This run tests a new issuer-specific reaction "
        "strength discriminator, not a nearby context-threshold retune."
    )
    payload["protocol_answers"]["3_single_causal_variable"] = (
        "sec_earnings_release_text_t1_strength_notional_scalar"
    )
    payload["related_files"] = [
        f"quant/experiments/{STEM}.py",
        _repo_rel(scout.OUT_JSON),
        _repo_rel(scout.DOC_LOG),
        _repo_rel(scout.DOC_TICKET),
        _repo_rel(scout.DOC_ARTIFACT),
        _repo_rel(scout.EXPERIMENT_LOG_JSONL),
    ]
    return payload


scout.build_payload = build_payload


if __name__ == "__main__":
    raise SystemExit(scout.main())
