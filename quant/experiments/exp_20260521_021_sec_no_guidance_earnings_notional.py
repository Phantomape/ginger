"""exp-20260521-021: SEC no-guidance earnings-release notional scout.

Tests whether earnings-release text that explicitly withholds, suspends, or
declines guidance deserves a bounded paper-sleeve notional scalar.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
import json
from pathlib import Path
import re
from typing import Any

import exp_20260519_012_sec_negative_reaction_absorption_notional as scout


EXPERIMENT_ID = "exp-20260521-021"
STEM = "exp_20260521_021_sec_no_guidance_earnings_notional"
TARGET_TEXT_EVENT_TYPE = "earnings_release_text"
TARGET_FIELD = "no_guidance_signal"
SCALAR_FIELD = "no_guidance_earnings_notional_scalar"
TRIAL_FAMILY = "sec_earnings_guidance_nonresponse_semantic_field"
BASELINE_SCALAR = 1.0

TARGET_SCALAR_VARIANTS: "OrderedDict[str, float]" = OrderedDict(
    [
        ("negative_reaction_scalar_0_70", 0.70),
        ("negative_reaction_scalar_0_85", 0.85),
        ("negative_reaction_scalar_1_00", 1.00),
        ("negative_reaction_scalar_1_10", 1.10),
    ]
)

NO_GUIDANCE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "explicit_no_guidance",
        re.compile(r"\b(?:no|without)\s+(?:financial\s+)?guidance\b", re.IGNORECASE),
    ),
    (
        "does_not_provide_guidance",
        re.compile(
            r"\b(?:do|does|did|will)\s+not\s+provide\s+(?:financial\s+)?guidance\b",
            re.IGNORECASE,
        ),
    ),
    (
        "not_providing_guidance",
        re.compile(
            r"\bnot\s+(?:providing|updating|reaffirming|issuing)\s+(?:financial\s+)?guidance\b",
            re.IGNORECASE,
        ),
    ),
    (
        "guidance_not_provided",
        re.compile(
            r"\b(?:guidance|outlook|forecast)\b.{0,80}\b(?:not\s+provided|not\s+updated|not\s+reaffirmed)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "guidance_withdrawn",
        re.compile(
            r"\b(?:withdraw|withdrew|withdrawn|suspend|suspended|suspending)\b.{0,80}\b(?:guidance|outlook|forecast)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
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
    / f"{EXPERIMENT_ID}_sec_no_guidance_earnings_notional.md"
)
scout.TARGET_SCALAR_VARIANTS = TARGET_SCALAR_VARIANTS
scout._ACTIVE_TARGET_SCALAR = 1.0

ORIGINAL_BUILD_PAYLOAD = scout.build_payload
ORIGINAL_PARENT_ANNOTATE = scout.parent._annotate_language_fields


def _text_for_accession(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    return str(row.get("combined_text") or row.get("text") or "")


def _accession(row: dict[str, Any]) -> str:
    return str(
        row.get("accession_number")
        or row.get("source_accession_number")
        or row.get("accession")
        or ""
    ).strip()


def _no_guidance_signals(text: str) -> dict[str, Any]:
    hits = [name for name, pattern in NO_GUIDANCE_PATTERNS if pattern.search(text)]
    return {
        TARGET_FIELD: bool(hits),
        "no_guidance_hit_count": len(hits),
        "no_guidance_hit_patterns": sorted(hits),
    }


def _annotate_no_guidance_fields(
    exp100: dict[str, Any],
    text_rows_by_accession: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    annotated = ORIGINAL_PARENT_ANNOTATE(exp100, text_rows_by_accession)
    for window_payload in annotated.get("windows", {}).values():
        for row in window_payload.get("candidate_rows", []) or []:
            text_row = text_rows_by_accession.get(_accession(row))
            row.update(_no_guidance_signals(_text_for_accession(text_row)))
    return annotated


scout.parent._annotate_language_fields = _annotate_no_guidance_fields


def _is_target_candidate(candidate: dict[str, Any]) -> bool:
    return (
        candidate.get("sec_text_coverage_status") == "covered"
        and candidate.get("text_event_type") == TARGET_TEXT_EVENT_TYPE
        and bool(candidate.get(TARGET_FIELD))
    )


def _is_target_position(position: dict[str, Any]) -> bool:
    source = scout._source_candidate(position)
    return bool(source and _is_target_candidate(source))


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
        rule_parts.append("no_guidance_earnings_release_scalar")
    return (
        float(scout.parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar,
        scalar,
        "+".join(rule_parts) or "default",
    )


def _target_coverage_summary(exp100: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    ticker_counter: Counter[str] = Counter()
    pattern_counter: Counter[str] = Counter()
    total_candidates = 0
    target_candidates = 0
    for window_name, window_payload in exp100.get("windows", {}).items():
        rows = window_payload.get("candidate_rows", []) or []
        targets = [row for row in rows if _is_target_candidate(row)]
        total_candidates += len(rows)
        target_candidates += len(targets)
        ticker_counter.update(str(row.get("ticker") or "") for row in targets)
        for row in targets:
            pattern_counter.update(row.get("no_guidance_hit_patterns") or [])
        by_window[window_name] = {
            "candidate_rows": len(rows),
            "target_rows": len(targets),
            "target_tickers": sorted({str(row.get("ticker") or "") for row in targets}),
            "target_accessions": sorted({_accession(row) for row in targets if _accession(row)}),
        }
    return {
        "total_candidate_rows": total_candidates,
        "target_candidate_rows": target_candidates,
        "target_share": (target_candidates / total_candidates) if total_candidates else 0.0,
        "by_window": by_window,
        "target_tickers": dict(sorted(ticker_counter.items())),
        "pattern_counts": dict(sorted(pattern_counter.items())),
    }


def _variant_key(name: str) -> str:
    return name.replace("negative_reaction", "no_guidance")


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
    selected = payload.get("best_variant") or gate.get("selected_variant") or "no_guidance_scalar_1_00"
    selected_summary = (payload.get("variant_summaries", {}) or {}).get(selected, {})
    target_coverage = payload.get("target_coverage", {}) or {}
    decision = payload.get("decision", "rejected_sec_no_guidance_earnings_notional")
    rejection_reason = payload.get("rejection_reason")
    if not rejection_reason and gate.get("sample_guard") is not None:
        sample_guard = gate.get("sample_guard") or {}
        if not sample_guard.get("passed", True):
            rejection_reason = sample_guard.get("reason")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload.get("timestamp"),
        "hypothesis": (
            "SEC earnings-release filings that explicitly withhold or decline guidance "
            "may have different continuation quality than other covered earnings-release events."
        ),
        "change_type": "alpha_search",
        "changed_variable": SCALAR_FIELD,
        "trial_accounting": payload.get("trial_accounting"),
        "parameters": {
            "target_text_event_type": TARGET_TEXT_EVENT_TYPE,
            "target_field": TARGET_FIELD,
            "scalar_variants": dict(TARGET_SCALAR_VARIANTS),
            "pattern_counts": target_coverage.get("pattern_counts"),
        },
        "backtest_protocol": payload.get("backtest_protocol"),
        "before_metrics": payload.get("before_metrics"),
        "after_metrics": selected_summary,
        "expected_value_score_delta": payload.get("expected_value_score_delta"),
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "More forward no-guidance earnings-release rows across tickers, or a richer "
            "guidance-quality semantic field that separates voluntary non-guidance from temporary uncertainty."
        ),
        "production_impact": payload.get("production_impact"),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload.get("gate", {}) or {}
    coverage = payload.get("target_coverage", {}) or {}
    selected = payload.get("best_variant") or gate.get("selected_variant") or "no_guidance_scalar_1_00"
    selected_summary = (payload.get("variant_summaries", {}) or {}).get(selected, {})
    lines = [
        f"# {EXPERIMENT_ID} SEC no-guidance earnings notional",
        "",
        "## Hypothesis",
        "Earnings-release filings that explicitly decline, suspend, or withhold guidance are a distinct continuation-quality cohort in the SEC financial-report paper sleeve.",
        "",
        "## Trial accounting",
        f"- trial_family: {TRIAL_FAMILY}",
        f"- changed_variable: {SCALAR_FIELD}",
        "- prior_trial_count: 3 nearby SEC earnings-release semantic notional scouts",
        "- nearby_prior_experiments: exp-20260516-034, exp-20260520-013, exp-20260520-015",
        "- multiple_testing_risk_bucket: moderate",
        "- new_evidence_type: new_sec_text_semantic_field",
        "",
        "## Gate",
        f"- decision: {payload.get('decision')}",
        f"- gate_passed: {gate.get('passed')}",
        f"- selected_variant: {selected}",
        f"- rejection_reason: {payload.get('rejection_reason')}",
        f"- checks: {json.dumps(gate.get('checks'), sort_keys=True)}",
        "",
        "## Target coverage",
        f"- target_candidate_rows: {coverage.get('target_candidate_rows')}",
        f"- target_share: {coverage.get('target_share')}",
        f"- target_tickers: {json.dumps(coverage.get('target_tickers'), sort_keys=True)}",
        f"- pattern_counts: {json.dumps(coverage.get('pattern_counts'), sort_keys=True)}",
        "",
        "## Selected metrics",
        "```json",
        json.dumps(selected_summary, indent=2, sort_keys=True),
        "```",
        "",
        "## Production impact",
        "No shared policy or live adapter changed. This is an offline paper-sleeve scout; promotion would require shared policy wiring and parity tests.",
    ]
    return "\n".join(lines) + "\n"


def build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    payload = _rename_variant_fields(payload)
    target_coverage = payload.get("target_coverage_summary", {}) or {}
    gate = payload.get("gate", {}) or {}
    aggregate_delta = gate.get("aggregate_delta", {}) or {}
    sample_guard = gate.get("sample_guard") or {}
    gate_passed = bool(gate.get("passed"))
    if gate_passed:
        status = "accepted_candidate"
        decision = "promising_sec_no_guidance_earnings_notional"
        interpretation = (
            "The no-guidance SEC earnings-release scalar cleared the paper-sleeve scout gate, "
            "but remains offline until moved into shared policy with parity tests."
        )
        rejection_reason = None
    else:
        status = "rejected"
        decision = "rejected_sec_no_guidance_earnings_notional"
        interpretation = (
            "No no-guidance earnings-release scalar cleared the three-window, tail-aware "
            "paper-sleeve gate on top of the accepted SEC stack."
        )
        rejection_reason = sample_guard.get("reason") or gate.get("reason") or interpretation
    best_variant = str(payload.get("best_variant") or "no_guidance_scalar_1_00")
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
                "SEC earnings-release rows with explicit no-guidance language form a "
                "separate continuation-quality cohort worth a bounded paper-sleeve scalar test."
            ),
            "change_summary": (
                "Sweep a bounded paper-notional scalar for covered earnings_release_text "
                "rows that explicitly withhold, decline, suspend, or withdraw guidance."
            ),
            "change_type": "alpha_search",
            "component": "offline_sec_financial_report_paper_sleeve_replay",
            "changed_variable": SCALAR_FIELD,
            "single_causal_variable": SCALAR_FIELD,
            "parameters": {
                "baseline_target_scalar": BASELINE_SCALAR,
                "target_scalar_variants": {
                    _variant_key(name): scalar
                    for name, scalar in TARGET_SCALAR_VARIANTS.items()
                },
                "best_target_scalar": best_scalar,
                "target_text_event_type": TARGET_TEXT_EVENT_TYPE,
                "target_field": TARGET_FIELD,
                "patterns": [name for name, _pattern in NO_GUIDANCE_PATTERNS],
                "accepted_earnings_release_spy_context_scalar": (
                    scout.ACCEPTED_EARNINGS_RELEASE_SPY_CONTEXT_SCALAR
                ),
                "base_event_notional_usd": float(scout.parent.DEFAULT_EVENT_NOTIONAL_USD),
                "max_positions": scout.parent.DEFAULT_MAX_POSITIONS,
                "anti_js": "No JavaScript was used.",
            },
            "trial_family": TRIAL_FAMILY,
            "trial_accounting": {
                "trial_family": TRIAL_FAMILY,
                "changed_variable": SCALAR_FIELD,
                "prior_trial_count": 3,
                "nearby_prior_experiments": [
                    "exp-20260516-034",
                    "exp-20260520-013",
                    "exp-20260520-015",
                ],
                "multiple_testing_risk_bucket": "moderate",
                "new_evidence_type": "new_sec_text_semantic_field",
            },
            "target_definition": {
                "text_event_type": TARGET_TEXT_EVENT_TYPE,
                "target_field": TARGET_FIELD,
                "patterns": [name for name, _pattern in NO_GUIDANCE_PATTERNS],
            },
            "target_coverage": target_coverage,
            "expected_value_score_delta": aggregate_delta.get("expected_value_score_sum_delta"),
            "total_pnl_delta": aggregate_delta.get("total_pnl_sum_delta"),
            "interpretation": interpretation,
            "rejection_reason": rejection_reason,
            "next_evidence_needed": (
                "More forward no-guidance earnings-release rows across tickers, or a richer "
                "guidance-quality semantic field that separates voluntary non-guidance from temporary uncertainty."
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
                    "LLM soft-ranking data remains sparse, so this deterministic SEC text field was tested instead."
                ),
            },
            "why_not_other_changes": (
                "Recent logs already rejected or exhausted nearby event governance/source scalars, "
                "broad-market local scalars, ETF pool additions, pilot sleeves, and LLM soft-ranking; "
                "this run used a distinct SEC earnings semantic field."
            ),
            "protocol_answers": {
                "alpha_hypothesis": (
                    "entry/allocation: no-guidance language may identify a weaker or stronger SEC earnings-release continuation cohort."
                ),
                "past_nearby_experiments": (
                    "Guidance raise, mixed-language, and clean-positive earnings-release notional scouts were tried; this run uses a different semantic non-response field."
                ),
                "single_causal_variable": SCALAR_FIELD,
                "acceptance_standard": (
                    "Same three-window protocol as docs/backtesting.md; retain only if aggregate EV/PnL improve without unacceptable window, tail, survival, or sample concentration issues."
                ),
                "reproducibility": (
                    "Script, JSON artifact, Markdown artifact, ticket, and experiment_log entry are committed."
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


def main() -> None:
    scout.main()


if __name__ == "__main__":
    main()
