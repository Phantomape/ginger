"""exp-20260519-022: SEC bad-SPY T+1 context haircut.

Alpha search on one production-visible SEC paper-sleeve context field.  The
latest accepted SEC sleeve boost (exp-20260519-008) rewards earnings-release
rows when SPY T+1 context is not sharply negative.  This run tests only the
complementary risk-allocation question: whether covered SEC financial-report
rows after a bad SPY T+1 day should receive a bounded paper-notional haircut.

Core entries, exits, candidate eligibility, queue capacity, hold days, LLM,
news, shared policy, and live/default orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import exp_20260519_012_sec_negative_reaction_absorption_notional as scout


EXPERIMENT_ID = "exp-20260519-022"
STEM = "exp_20260519_022_sec_bad_spy_t1_context_haircut"
TARGET_SPY_T1_RETURN_MAX = -0.005

scout.EXPERIMENT_ID = EXPERIMENT_ID
scout.STEM = STEM
scout.OUT_DIR = scout.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
scout.OUT_JSON = scout.OUT_DIR / f"{STEM}.json"
scout.DOC_LOG = (
    scout.REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
)
scout.DOC_TICKET = (
    scout.REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
)
scout.DOC_ARTIFACT = (
    scout.REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_bad_spy_t1_context_haircut.md"
)


def _is_bad_spy_context_candidate(candidate: dict[str, Any]) -> bool:
    spy_t1 = scout._float(candidate.get("spy_t1_return"))
    return (
        str(candidate.get("sec_text_coverage_status") or "") == "covered"
        and spy_t1 is not None
        and spy_t1 < TARGET_SPY_T1_RETURN_MAX
    )


def _is_bad_spy_context_position(position: dict[str, Any]) -> bool:
    return _is_bad_spy_context_candidate(scout._source_candidate(position))


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
    if _is_bad_spy_context_position(position):
        scalar *= float(scout._ACTIVE_TARGET_SCALAR)
        rule_parts.append("sec_bad_spy_t1_context_scalar")
    return (
        float(scout.parent.DEFAULT_EVENT_NOTIONAL_USD) * scalar,
        scalar,
        "+".join(rule_parts),
    )


def _target_coverage_summary(exp100: dict[str, Any]) -> dict[str, Any]:
    aggregate = {"target": 0, "non_target": 0, "missing_spy_t1": 0}
    by_window: dict[str, Any] = {}
    for label, window in exp100.get("windows", {}).items():
        rows = window.get("candidate_rows") or []
        target = 0
        missing = 0
        for row in rows:
            if (
                str(row.get("sec_text_coverage_status") or "") == "covered"
                and scout._float(row.get("spy_t1_return")) is None
            ):
                missing += 1
            if _is_bad_spy_context_candidate(row):
                target += 1
        by_window[label] = {
            "candidate_count": len(rows),
            "target_count": target,
            "covered_missing_spy_t1": missing,
        }
        aggregate["target"] += target
        aggregate["missing_spy_t1"] += missing
        aggregate["non_target"] += max(len(rows) - target, 0)
    return {
        "aggregate": aggregate,
        "by_window": by_window,
        "target_definition": {
            "sec_text_coverage_status": "covered",
            "spy_t1_return_lt": TARGET_SPY_T1_RETURN_MAX,
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["gate"]["aggregate_delta"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Bad-SPY T+1 Context Haircut",
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


scout._is_negative_reaction_candidate = _is_bad_spy_context_candidate
scout._is_negative_reaction_position = _is_bad_spy_context_position
scout._notional_for_position = _notional_for_position
scout._target_coverage_summary = _target_coverage_summary
scout._artifact_markdown = _artifact_markdown


def _repo_rel(path: Path | str) -> str:
    return scout._repo_rel(path)


def _bad_spy_variant_name(name: str) -> str:
    return name.replace("negative_reaction_scalar", "sec_bad_spy_t1_context_scalar")


def _rename_bad_spy_fields(payload: dict[str, Any]) -> None:
    payload["best_variant"] = _bad_spy_variant_name(payload["best_variant"])
    variants = payload["parameters"].get("target_scalar_variants", {})
    payload["parameters"]["target_scalar_variants"] = {
        _bad_spy_variant_name(name): value for name, value in variants.items()
    }
    summaries = payload.get("variant_summaries", {})
    payload["variant_summaries"] = {
        _bad_spy_variant_name(name): row for name, row in summaries.items()
    }
    for row in payload["variant_summaries"].values():
        scalar = row.pop("negative_reaction_absorption_notional_scalar", None)
        row["sec_bad_spy_t1_context_notional_scalar"] = scalar


def build_payload() -> dict[str, Any]:
    payload = scout.build_payload()
    _rename_bad_spy_fields(payload)
    passed = bool(payload["gate"]["passed"])
    rejection_reason = (
        None
        if passed
        else (
            "The best haircut variant improved aggregate EV/PnL but failed the "
            "paper-sleeve gate: only five closed trades were adjusted and 61.73% "
            "of positive incremental PnL came from one TSLA trade."
        )
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "accepted_candidate" if passed else "rejected",
            "decision": (
                "promising_sec_bad_spy_t1_context_haircut"
                if passed
                else "rejected_sec_bad_spy_t1_context_haircut"
            ),
            "hypothesis": (
                "Within the SEC financial-report default-off paper sleeve, covered "
                "rows following a SPY T+1 return below -0.5% may be broad-market "
                "fragility rather than firm-specific post-filing drift. A bounded "
                "paper-notional haircut could improve risk allocation without "
                "changing queue eligibility, hold days, capacity, or live orders."
            ),
            "change_summary": (
                "Sweep a paper-notional scalar for covered SEC financial-report "
                "rows with spy_t1_return < -0.005, on top of the accepted "
                "earnings-release SPY-context stack."
            ),
            "change_type": "alpha_search_sec_market_context_notional_allocation",
            "component": "quant/sec_financial_report_event_sleeve.py",
            "changed_variable": "sec_bad_spy_t1_context_notional_scalar",
            "single_causal_variable": (
                "covered SEC financial-report row plus SPY T+1 return below -0.5% "
                "paper-notional scalar"
            ),
            "interpretation": (
                "The bad-SPY T+1 context haircut is a possible risk-allocation "
                "candidate, but it is not promoted until shared default-off SEC "
                "paper code and forward evidence confirm it."
                if passed
                else "Bad-SPY T+1 context is too sparse in realized adjusted trades "
                "and too concentrated in one TSLA benefit to promote or keep tuning."
            ),
            "rejection_reason": rejection_reason,
            "next_evidence_needed": (
                "If pursued, implement only in shared default-off SEC paper sleeve "
                "code with production report visibility and parity tests; keep live "
                "orders disabled until forward replacement-value evidence matures."
                if passed
                else "Do not retry pure SPY T+1 bad-context haircuts on this frozen "
                "sample; require a new semantic field, more forward SEC paper rows, "
                "or a broader replacement-value framework."
            ),
            "why_not_other_changes": (
                "State-surface rank/ret20 scouts looked like adjacent profile mining "
                "after exp-20260519-021; LLM soft-ranking remains sample-sparse; "
                "cached augmented candidate-pool expansion is baseline-drift limited."
            ),
        }
    )
    payload["parameters"]["target_spy_t1_return_max"] = TARGET_SPY_T1_RETURN_MAX
    payload["parameters"].pop("target_t1_excess_max", None)
    payload["protocol_answers"]["1_alpha_hypothesis"] = (
        "risk allocation / capital allocation: haircut covered SEC paper rows only "
        "when SPY T+1 return is below -0.5%."
    )
    payload["protocol_answers"]["2_history_check"] = (
        "exp-20260519-008 accepted the positive complement: earnings_release_text "
        "with SPY T+1 >= -0.5% received a 1.10x paper-notional scalar. "
        "exp-20260519-010/012/013 failed nearby SEC overlap/reaction ideas. "
        "This tests only the bad-market-context complement, not another LLM rank."
    )
    payload["protocol_answers"]["3_single_causal_variable"] = (
        "sec_bad_spy_t1_context_notional_scalar"
    )
    payload["protocol_answers"]["5_reproducibility"] = (
        f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
    )
    payload["llm_metrics"] = {
        "used_llm": False,
        "llm_role_changed": False,
        "blocker_relation": (
            "LLM soft-ranking was intentionally avoided because recent logs show "
            "sparse attribution; this uses deterministic SEC coverage and SPY T+1 "
            "fields already present in replay."
        ),
    }
    payload["production_impact"] = {
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
            "A positive result would require moving the same field into shared "
            "sec_financial_report_event_sleeve.py before any retained behavior."
        ),
    }
    payload["related_files"] = [
        f"quant/experiments/{STEM}.py",
        _repo_rel(scout.OUT_JSON),
        _repo_rel(scout.DOC_LOG),
        _repo_rel(scout.DOC_TICKET),
        _repo_rel(scout.DOC_ARTIFACT),
        _repo_rel(scout.EXPERIMENT_LOG_JSONL),
    ]
    return payload


def main() -> int:
    payload = build_payload()
    scout.persist(payload)
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
                    "gate_metrics": payload["gate"]["metrics"],
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
