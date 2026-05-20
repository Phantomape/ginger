"""exp-20260520-015: SEC clean-positive earnings-release notional scout.

Alpha search on one production-visible SEC paper-sleeve semantic field. This
tests covered ``earnings_release_text`` rows that are classified as positive
language while carrying no negative phrase or guidance-cut hits. The goal is to
separate clean positive factual/tone alignment from the broader positive
language bucket, without expanding LLM authority, candidate eligibility, queue
capacity, hold days, exits, or live/default orders.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import exp_20260519_012_sec_negative_reaction_absorption_notional as scout


EXPERIMENT_ID = "exp-20260520-015"
STEM = "exp_20260520_015_sec_clean_positive_earnings_notional"
TARGET_LANGUAGE_BUCKET = "positive_language"
TARGET_TEXT_EVENT_TYPE = "earnings_release_text"
TARGET_NEGATIVE_HITS_MAX = 0
TARGET_GUIDANCE_CUT_HITS_MAX = 0
TARGET_POSITIVE_OR_GUIDANCE_HITS_MIN = 1

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
    / f"{EXPERIMENT_ID}_sec_clean_positive_earnings_notional.md"
)
scout.TARGET_SCALAR_VARIANTS = OrderedDict(
    [
        ("negative_reaction_scalar_0_00", 0.00),
        ("negative_reaction_scalar_0_50", 0.50),
        ("negative_reaction_scalar_0_75", 0.75),
        ("negative_reaction_scalar_0_90", 0.90),
        ("negative_reaction_scalar_1_00", 1.00),
        ("negative_reaction_scalar_1_05", 1.05),
        ("negative_reaction_scalar_1_10", 1.10),
        ("negative_reaction_scalar_1_25", 1.25),
        ("negative_reaction_scalar_1_50", 1.50),
    ]
)
ORIGINAL_BUILD_PAYLOAD = scout.build_payload


def _hit_count(value: Any) -> int:
    if isinstance(value, (list, tuple, set)):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    number = scout._float(value)
    if number is not None:
        return int(number)
    text = str(value or "").strip()
    return 1 if text else 0


def _semantic_hits(candidate: dict[str, Any]) -> dict[str, int]:
    return {
        "positive_phrase_hits": _hit_count(candidate.get("positive_phrase_hits")),
        "negative_phrase_hits": _hit_count(candidate.get("negative_phrase_hits")),
        "guidance_raise_hits": _hit_count(candidate.get("guidance_raise_hits")),
        "guidance_cut_hits": _hit_count(candidate.get("guidance_cut_hits")),
    }


def _is_target_candidate(candidate: dict[str, Any]) -> bool:
    hits = _semantic_hits(candidate)
    positive_or_guidance_hits = (
        hits["positive_phrase_hits"] + hits["guidance_raise_hits"]
    )
    return (
        str(candidate.get("sec_text_coverage_status") or "") == "covered"
        and str(candidate.get("text_event_type") or "") == TARGET_TEXT_EVENT_TYPE
        and str(candidate.get("language_bucket") or "") == TARGET_LANGUAGE_BUCKET
        and hits["negative_phrase_hits"] <= TARGET_NEGATIVE_HITS_MAX
        and hits["guidance_cut_hits"] <= TARGET_GUIDANCE_CUT_HITS_MAX
        and positive_or_guidance_hits >= TARGET_POSITIVE_OR_GUIDANCE_HITS_MIN
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
        rule_parts.append("clean_positive_earnings_release_scalar")
    return (
        float(scout.parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar,
        scalar,
        "+".join(rule_parts),
    )


def _target_coverage_summary(exp100: dict[str, Any]) -> dict[str, Any]:
    aggregate = {"target": 0, "non_target": 0}
    by_window: dict[str, Any] = {}
    by_ticker = Counter()
    hit_profiles = Counter()
    for label, window in exp100.get("windows", {}).items():
        rows = window.get("candidate_rows") or []
        target = 0
        for row in rows:
            hits = _semantic_hits(row)
            if _is_target_candidate(row):
                target += 1
                by_ticker[str(row.get("ticker") or "missing")] += 1
                hit_profiles[
                    "{positive}p_{negative}n_{raise_hits}gr_{cut}gc".format(
                        positive=hits["positive_phrase_hits"],
                        negative=hits["negative_phrase_hits"],
                        raise_hits=hits["guidance_raise_hits"],
                        cut=hits["guidance_cut_hits"],
                    )
                ] += 1
        by_window[label] = {
            "candidate_count": len(rows),
            "target_count": target,
        }
        aggregate["target"] += target
        aggregate["non_target"] += max(len(rows) - target, 0)
    return {
        "aggregate": aggregate,
        "by_window": by_window,
        "target_definition": {
            "sec_text_coverage_status": "covered",
            "text_event_type": TARGET_TEXT_EVENT_TYPE,
            "language_bucket": TARGET_LANGUAGE_BUCKET,
            "negative_phrase_hits_lte": TARGET_NEGATIVE_HITS_MAX,
            "guidance_cut_hits_lte": TARGET_GUIDANCE_CUT_HITS_MAX,
            "positive_phrase_plus_guidance_raise_hits_gte": (
                TARGET_POSITIVE_OR_GUIDANCE_HITS_MIN
            ),
        },
        "target_ticker_counts": dict(sorted(by_ticker.items())),
        "target_hit_profiles": dict(sorted(hit_profiles.items())),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["gate"]["aggregate_delta"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Clean-Positive Earnings-Release Notional",
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
            "## Coverage",
            "",
            "```json",
            json.dumps(
                scout._safe(payload["target_coverage_summary"]),
                indent=2,
                sort_keys=True,
            ),
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
        "clean_positive_earnings_scalar",
    )
    variants = payload["parameters"].get("target_scalar_variants", {})
    payload["parameters"]["target_scalar_variants"] = {
        name.replace("negative_reaction_scalar", "clean_positive_earnings_scalar"): value
        for name, value in variants.items()
    }
    summaries = payload.get("variant_summaries", {})
    payload["variant_summaries"] = {
        name.replace("negative_reaction_scalar", "clean_positive_earnings_scalar"): row
        for name, row in summaries.items()
    }
    for row in summaries.values():
        scalar = row.pop("negative_reaction_absorption_notional_scalar", None)
        row["clean_positive_earnings_notional_scalar"] = scalar


def build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    _rename_variant_fields(payload)
    passed = bool(payload["gate"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "decision": (
                "promising_sec_clean_positive_earnings_notional"
                if passed
                else "rejected_sec_clean_positive_earnings_notional"
            ),
            "hypothesis": (
                "Within the SEC financial-report default-off paper sleeve, "
                "covered earnings_release_text rows with positive_language and "
                "no negative phrase or guidance-cut hits may represent cleaner "
                "fact/tone alignment than the broad positive-language bucket. "
                "A bounded paper-notional scalar may improve allocation without "
                "changing queue eligibility, hold days, capacity, LLM authority, "
                "or live orders."
            ),
            "change_summary": (
                "Sweep a paper-notional scalar for covered clean-positive SEC "
                "earnings-release rows."
            ),
            "change_type": "alpha_search_semantic_notional_allocation",
            "component": "quant/sec_financial_report_event_sleeve.py",
            "changed_variable": "sec_clean_positive_earnings_notional_scalar",
            "single_causal_variable": (
                "clean-positive earnings-release paper-notional scalar"
            ),
            "interpretation": (
                "Clean-positive SEC earnings-release rows cleared the paper-sleeve "
                "scout gate as an allocation candidate. Promotion requires moving "
                "the same rule into shared default-off SEC paper sleeve code with "
                "parity tests."
                if passed
                else "No clean-positive earnings-release scalar cleared the "
                "three-window, tail-aware paper-sleeve gate on top of the latest "
                "accepted SEC stack."
            ),
            "rejection_reason": None
            if passed
            else (
                "No clean-positive earnings-release scalar cleared the "
                "three-window, tail-aware paper-sleeve gate."
            ),
            "next_evidence_needed": (
                "Implement only in shared default-off SEC paper sleeve code with "
                "production report visibility and parity tests; keep live orders "
                "disabled until forward replacement-value evidence matures."
                if passed
                else "Do not retry nearby positive-language phrase-hit scalars "
                "on the frozen sample without a richer semantic field such as "
                "explicit guidance-delta extraction, management non-response, "
                "or forward replacement-value evidence."
            ),
            "why_not_other_changes": (
                "State-surface scalar/profile mining is under the strict 10% "
                "anti-repeat gate; broad-market local scalars have just failed "
                "or identity-control drift; LLM soft-ranking lacks replay-safe "
                "attribution. Recent SEC neutral, mixed-message, and reaction "
                "scalars failed sample/tail gates, so this tests a conflict-free "
                "semantic field rather than another reaction bucket."
            ),
            "protocol_answers": {
                "1_alpha_hypothesis": (
                    "capital allocation / event semantic field: scale SEC paper "
                    "rows only when text_event_type=earnings_release_text, "
                    "language_bucket=positive_language, negative_phrase_hits=0, "
                    "guidance_cut_hits=0, and positive or guidance-raise evidence "
                    "is present. This matches the playbook priority for SEC "
                    "semantic expansion and avoids sparse LLM soft-ranking."
                ),
                "2_history_check": (
                    "exp-20260518-012 rejected broad positive-language notional; "
                    "exp-20260520-008 rejected positive-language low-reaction; "
                    "exp-20260520-013 rejected mixed-message positive-plus-negative "
                    "phrase hits. No prior run isolated clean positive earnings "
                    "release text with zero negative/cut hits."
                ),
                "3_single_causal_variable": (
                    "sec_clean_positive_earnings_notional_scalar"
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
    payload["parameters"]["target_negative_hits_max"] = TARGET_NEGATIVE_HITS_MAX
    payload["parameters"]["target_guidance_cut_hits_max"] = (
        TARGET_GUIDANCE_CUT_HITS_MAX
    )
    payload["parameters"]["target_positive_or_guidance_hits_min"] = (
        TARGET_POSITIVE_OR_GUIDANCE_HITS_MIN
    )
    return payload


scout.build_payload = build_payload


def main() -> int:
    return scout.main()


if __name__ == "__main__":
    raise SystemExit(main())
