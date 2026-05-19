"""exp-20260519-013: SEC negative-language confirmed reaction notional.

Alpha search on one SEC paper-sleeve field interaction.  The broad
negative-language scalar was rejected in exp-20260518-011, so this run tests a
narrower production-visible branch: covered ``negative_language`` rows whose
T+1 excess return versus SPY is at least +2%.  The +2% boundary reuses the
accepted neutral-underreaction cutoff in reverse, rather than mining a nearby
free threshold.

Core entries, exits, candidate eligibility, queue capacity, hold days, LLM,
news, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import exp_20260519_012_sec_negative_reaction_absorption_notional as scout


EXPERIMENT_ID = "exp-20260519-013"
STEM = "exp_20260519_013_sec_negative_language_confirmed_reaction_notional"
TARGET_T1_EXCESS_MIN = 0.02

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
    / f"{EXPERIMENT_ID}_sec_negative_language_confirmed_reaction_notional.md"
)


def _is_confirmed_reaction_candidate(candidate: dict[str, Any]) -> bool:
    t1_excess = scout._float(candidate.get("t1_excess_return_vs_spy"))
    return (
        str(candidate.get("sec_text_coverage_status") or "") == "covered"
        and str(candidate.get("language_bucket") or "") == "negative_language"
        and t1_excess is not None
        and t1_excess >= TARGET_T1_EXCESS_MIN
    )


def _is_confirmed_reaction_position(position: dict[str, Any]) -> bool:
    return _is_confirmed_reaction_candidate(scout._source_candidate(position))


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
    if _is_confirmed_reaction_position(position):
        scalar *= float(scout._ACTIVE_TARGET_SCALAR)
        rule_parts.append("negative_language_confirmed_reaction_scalar")
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
                and str(row.get("language_bucket") or "") == "negative_language"
                and scout._float(row.get("t1_excess_return_vs_spy")) is None
            ):
                missing += 1
            if _is_confirmed_reaction_candidate(row):
                target += 1
        by_window[label] = {
            "candidate_count": len(rows),
            "target_count": target,
            "negative_language_missing_t1_excess": missing,
        }
        aggregate["target"] += target
        aggregate["missing_t1_excess"] += missing
        aggregate["non_target"] += max(len(rows) - target, 0)
    return {
        "aggregate": aggregate,
        "by_window": by_window,
        "target_definition": {
            "sec_text_coverage_status": "covered",
            "language_bucket": "negative_language",
            "t1_excess_return_vs_spy_gte": TARGET_T1_EXCESS_MIN,
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["gate"]["aggregate_delta"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Negative-Language Confirmed Reaction Notional",
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


scout._is_negative_reaction_candidate = _is_confirmed_reaction_candidate
scout._is_negative_reaction_position = _is_confirmed_reaction_position
scout._notional_for_position = _notional_for_position
scout._target_coverage_summary = _target_coverage_summary
scout._artifact_markdown = _artifact_markdown


def _repo_rel(path: Path | str) -> str:
    return scout._repo_rel(path)


def _confirmed_variant_name(name: str) -> str:
    return name.replace("negative_reaction_scalar", "confirmed_reaction_scalar")


def _rename_confirmed_reaction_fields(payload: dict[str, Any]) -> None:
    payload["best_variant"] = _confirmed_variant_name(payload["best_variant"])
    variants = payload["parameters"].get("target_scalar_variants", {})
    payload["parameters"]["target_scalar_variants"] = {
        _confirmed_variant_name(name): value for name, value in variants.items()
    }
    summaries = payload.get("variant_summaries", {})
    payload["variant_summaries"] = {
        _confirmed_variant_name(name): row for name, row in summaries.items()
    }
    for row in payload["variant_summaries"].values():
        scalar = row.pop("negative_reaction_absorption_notional_scalar", None)
        row["negative_language_confirmed_reaction_notional_scalar"] = scalar


def build_payload() -> dict[str, Any]:
    payload = scout.build_payload()
    _rename_confirmed_reaction_fields(payload)
    passed = bool(payload["gate"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "decision": (
                "promising_sec_negative_language_confirmed_reaction_notional"
                if passed
                else "rejected_sec_negative_language_confirmed_reaction_notional"
            ),
            "hypothesis": (
                "Within the SEC financial-report default-off paper sleeve, covered "
                "negative_language rows with strong positive T+1 excess reaction "
                "may represent market-confirmed bad-news absorption. A bounded "
                "paper-notional scalar may improve allocation without changing "
                "queue eligibility, hold days, capacity, or live orders."
            ),
            "change_summary": (
                "Sweep a paper-notional scalar for covered negative_language SEC "
                "rows with t1_excess_return_vs_spy >= 0.02."
            ),
            "changed_variable": (
                "sec_negative_language_t1_confirmed_reaction_notional_scalar"
            ),
            "single_causal_variable": (
                "negative-language plus T+1 excess >= 2% paper-notional scalar"
            ),
            "interpretation": (
                "Negative-language SEC rows with confirmed positive T+1 excess "
                "reaction cleared the paper-sleeve scout gate as an allocation "
                "candidate. It is not promoted to production behavior in this run."
                if passed
                else "No confirmed-reaction scalar cleared the three-window, "
                "tail-aware paper-sleeve gate on top of the latest accepted SEC stack."
            ),
            "rejection_reason": None
            if passed
            else (
                "No confirmed-reaction scalar cleared the three-window, tail-aware "
                "paper-sleeve gate on top of the latest accepted SEC stack."
            ),
            "next_evidence_needed": (
                "If pursued, implement only in shared default-off SEC paper sleeve "
                "code with production report visibility and parity tests; keep live "
                "orders disabled until forward replacement-value evidence matures."
                if passed
                else "Do not retry nearby negative-language/reaction scalars on the "
                "frozen sample without a new semantic field or forward evidence."
            ),
            "why_not_other_changes": (
                "Candidate-pool expansion is blocked by augmented snapshot baseline "
                "drift; state-surface near-high/profile mining is anti-repeat; broad "
                "negative-language scalar already failed."
            ),
        }
    )
    payload["parameters"]["target_t1_excess_min"] = TARGET_T1_EXCESS_MIN
    payload["parameters"].pop("target_t1_excess_max", None)
    payload["protocol_answers"]["1_alpha_hypothesis"] = (
        "capital allocation: scale SEC paper rows only when "
        "language_bucket=negative_language and t1_excess_return_vs_spy >= 0.02."
    )
    payload["protocol_answers"]["2_history_check"] = (
        "exp-20260518-011 rejected broad negative-language notional; this run "
        "tests the narrower confirmed-reaction branch using the existing 2% "
        "neutral-underreaction boundary in reverse."
    )
    payload["protocol_answers"]["3_single_causal_variable"] = (
        "sec_negative_language_t1_confirmed_reaction_notional_scalar"
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


def persist(payload: dict[str, Any]) -> None:
    scout.persist(payload)


def main() -> int:
    payload = build_payload()
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
                    "selection": payload["selection"],
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
