"""exp-20260621-013: post-scalar-stack direction gate.

Alpha-search blocker. This run does not add a strategy rule. It asks whether
the next alpha can be evaluated honestly after the accepted source-scalar stack
and the latest SEC/proxy attempts. If no candidate has non-frozen PIT evidence
and three-window sample coverage, strategy edits are blocked.

No JavaScript is used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import exp_20260621_009_post_scalar_stack_nonrepeat_readiness as prior


EXPERIMENT_ID = "exp-20260621-013"
SLUG = "post_scalar_direction_gate"
RUNNER_NAME = f"quant/experiments/exp_20260621_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

HYPOTHESIS = (
    "candidate_pool/data-edge direction gate: after the accepted source-scalar "
    "stack and the latest SEC debt-text rejection, a new alpha should proceed "
    "only if it has non-frozen PIT evidence and three-window sample coverage; "
    "otherwise the credible alpha action is blocked."
)

TRIAL_FAMILY = "post_scalar_direction_gate"
TRIAL_VARIANT_ID = "post_exp_20260621_012_direction_gate_v1"
CHANGED_VARIABLE = (
    "current post-scalar candidate-pool alpha surfaces must demonstrate "
    "non-frozen PIT data edge plus three-window coverage before strategy code "
    "changes"
)

RECENT_EVIDENCE = [
    "exp-20260621-009",
    "exp-20260621-010",
    "exp-20260621-011",
    "exp-20260621-012",
    "exp-20260620-032",
    "exp-20260621-001",
    "exp-20260621-006",
    "exp-20260621-007",
    "exp-20260621-008",
]


def configure_prior_module() -> None:
    data_dir = prior.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.SLUG = SLUG
    prior.RUNNER_NAME = RUNNER_NAME
    prior.RUNNER_COMMAND = RUNNER_COMMAND
    prior.DATA_DIR = data_dir
    prior.ARTIFACT_JSON = data_dir / f"exp_20260621_013_{SLUG}.json"
    prior.BEFORE_JSON = data_dir / "before_baseline.json"
    prior.AFTER_JSON = data_dir / "after_no_strategy_change.json"
    prior.README_MD = data_dir / "README.md"
    prior.LOG_JSON = prior.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    prior.CARD_MD = prior.REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
    prior.MANIFEST_JSON = (
        prior.REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
    )
    prior.TICKET_JSON = (
        prior.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    prior.HYPOTHESIS = HYPOTHESIS
    prior.PRIOR_BLOCKERS = RECENT_EVIDENCE


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: post-scalar direction gate",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- Strategy / production behavior changed: no",
        "",
        "## Gate 4 Baseline",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in prior.CANONICAL_WINDOWS.items():
        lines.append(
            f"| {label} | {row['expected_value_score']:.4f} | "
            f"{row['expected_value_score']:.4f} | 0.0000 | "
            f"${row['total_pnl']:,.2f} | ${row['total_pnl']:,.2f} | $0.00 |"
        )

    aggregate = result["gate4"]["aggregate_before"]
    remaining = result["gate3"]["remaining_unscaled_source_sample"]
    lines.extend(
        [
            "",
            "## Blocker",
            "",
            f"Aggregate baseline EV `{aggregate['aggregate_expected_value_score']:.4f}`, "
            f"PnL `${aggregate['aggregate_total_pnl']:,.2f}`. No after policy was run.",
            "",
            "Remaining unscaled allocator source sample:",
            "",
        ]
    )
    for source, row in remaining.items():
        lines.append(
            f"- `{source}`: `{row['selected_trade_count']}` selected rows, "
            f"windows `{row['windows_with_selected_rows']}`."
        )
    lines.extend(
        [
            "",
            "Latest failed surfaces:",
            "",
            "- `exp-20260621-011`: proxy residual idiosyncratic leadership was positive in aggregate but failed window/comparator/drawdown checks.",
            "- `exp-20260621-012`: SEC credit agreement / term loan no-covenant text produced zero target trades.",
            "",
            result["post_run_reflection"]["best_next_alpha_direction"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_result() -> dict[str, Any]:
    result = prior.build_result()
    result.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "decision": "blocked_no_gate4_ready_alpha_after_latest_post_scalar_evidence",
            "change_type": "direction_gate_blocker",
            "mechanism_family": "candidate_pool_data_edge_readiness",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "reproduction": RUNNER_COMMAND,
        }
    )
    result["gate2"]["latest_post_scalar_evidence"] = {
        "exp-20260621-011": prior.prior_summary("exp-20260621-011"),
        "exp-20260621-012": prior.prior_summary("exp-20260621-012"),
        "new_evidence_axis": (
            "Post-exp-20260621-012 allocator/source-count audit plus latest "
            "SEC debt-text zero-sample evidence; this is a blocker proof, not "
            "a frozen family retry."
        ),
    }
    result["gate2"]["blocking_item"] = (
        "No current candidate source has all of: non-frozen novelty, PIT-safe "
        "runtime fields, three canonical windows, enough target/sample rows, "
        "and shared-paper-first production parity."
    )
    result["gate4"]["reason"] = (
        "Gate 2/Gate 3 blocked all reviewed alpha surfaces, so after intentionally "
        "equals before across the three canonical windows."
    )
    result["production_impact"]["parity_note"] = (
        "No production/backtest inconsistency was introduced because no trading "
        "rule or shared helper changed. A future positive alpha must be "
        "implemented shared-paper-first before it can be accepted."
    )
    result["calibration"]["failure_modes_observed"] = [
        "remaining_allocator_sources_sample_starved",
        "proxy_residual_leadership_failed_window_comparator_and_drawdown_checks",
        "sec_debt_text_no_covenant_candidate_had_zero_target_trades",
        "sec_companyfacts_relation_families_near_neighbor_or_rejected",
        "no_new_pit_runtime_field_with_three_window_coverage",
    ]
    result["post_run_reflection"] = {
        "why_blocked": (
            "The accepted source-scalar stack already scales every meaningful "
            "selected source. The remaining unscaled sources are zero- or "
            "two-row samples, exp-20260621-011 failed distribution/window "
            "comparators despite aggregate lift, and exp-20260621-012 produced "
            "zero target trades. Running another mined Companyfacts, SEC phrase, "
            "or allocator tweak would be a near-neighbor replay rather than a "
            "credible alpha test."
        ),
        "negative_result_reflection": (
            "This is a blocked alpha-search result, not a losing after-policy. "
            "The failure mode is data-edge exhaustion: positive-looking broad "
            "OHLCV proxies are not stable enough across windows, while free SEC "
            "text/fact variants either do not fire, lack PIT-safe structured "
            "fields, or fail the accepted allocator comparator."
        ),
        "best_next_alpha_direction": (
            "Optimize candidate-pool alpha only after adding a fresh free PIT "
            "data source with closed rows: CIK-level customer/supplier/contract "
            "economics from primary SEC documents, historical 10-K/10-Q "
            "cover-page filer status by accession, PIT analyst breadth or "
            "revenue-estimate dispersion, or borrow/options as-of rows with "
            "fixed-window coverage."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry source rank/notional/top-N/cooldown, daily second slot, "
            "generic SEC item or phrase screens, current SEC submission category, "
            "Companyfacts ratio thresholds, or OHLCV proxy residual leadership "
            "without a materially new PIT field or closed forward replacement rows."
        ),
    }
    result["changed_files"] = [
        RUNNER_NAME,
        prior.repo_rel(prior.ARTIFACT_JSON),
        prior.repo_rel(prior.BEFORE_JSON),
        prior.repo_rel(prior.AFTER_JSON),
        prior.repo_rel(prior.README_MD),
        prior.repo_rel(prior.LOG_JSON),
        prior.repo_rel(prior.CARD_MD),
        prior.repo_rel(prior.MANIFEST_JSON),
        prior.repo_rel(prior.TICKET_JSON),
        "docs/experiment_log.jsonl",
        "docs/experiment_registry.json",
    ]
    return result


def update_ticket(result: dict[str, Any]) -> None:
    ticket = prior.read_json(prior.TICKET_JSON)
    ticket.update(
        {
            "status": result["status"],
            "completed_at": result["timestamp"],
            "decision": result["decision"],
            "summary": result["post_run_reflection"]["why_blocked"],
            "result": {
                "decision": result["decision"],
                "artifact": prior.repo_rel(prior.ARTIFACT_JSON),
                "before": prior.repo_rel(prior.BEFORE_JSON),
                "after": prior.repo_rel(prior.AFTER_JSON),
                "log": prior.repo_rel(prior.LOG_JSON),
                "aggregate_expected_value_delta": 0.0,
                "aggregate_strategy_total_pnl_delta": 0.0,
                "accepted": False,
                "accepted_alpha": False,
                "gate4": result["gate4"],
                "production_impact": result["production_impact"],
                "lean_quality_passed": result["lean_quality_passed"],
            },
        }
    )
    prior.write_json(prior.TICKET_JSON, ticket)


def refresh_registry(result: dict[str, Any]) -> None:
    existing_ticket = prior.read_json(prior.TICKET_JSON)
    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": prior.repo_rel(prior.ARTIFACT_JSON),
        "before": prior.repo_rel(prior.BEFORE_JSON),
        "after": prior.repo_rel(prior.AFTER_JSON),
        "log": prior.repo_rel(prior.LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_blocked"],
    }
    fields = dict(existing_ticket)
    fields.update(
        {
            "owner": "alpha-search-automation",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": RECENT_EVIDENCE,
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": (
                "post-latest-run allocator/source-count and SEC-family blocker proof"
            ),
            "baseline_result_file": prior.BASELINE_RESULT_FILE,
            "evaluation_windows": [
                {
                    "label": label,
                    "start": row["start"],
                    "end": row["end"],
                    "snapshot": row["snapshot"],
                }
                for label, row in prior.CANONICAL_WINDOWS.items()
            ],
            "acceptance_rule": (
                "Blocked unless a current alpha candidate has non-frozen PIT "
                "evidence, runtime fields, survival >=5%, and all three canonical "
                "windows available for before/after Gate 4."
            ),
            "decision": result["decision"],
            "summary": result["post_run_reflection"]["why_blocked"],
            "artifact": prior.repo_rel(prior.ARTIFACT_JSON),
            "before": prior.repo_rel(prior.BEFORE_JSON),
            "after": prior.repo_rel(prior.AFTER_JSON),
            "log": prior.repo_rel(prior.LOG_JSON),
            "card_file": prior.repo_rel(prior.CARD_MD),
            "revision_manifest_file": prior.repo_rel(prior.MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "lean_quality_passed": result["lean_quality_passed"],
        }
    )
    prior.experiment_registry.persist_self_registered_result(
        prior.REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status=result["status"],
        fields=fields,
    )


def main() -> None:
    configure_prior_module()
    prior.build_card = build_card
    result = build_result()
    prior.persist(result)
    refresh_registry(result)
    update_ticket(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "remaining_unscaled_sources": result["gate3"][
                    "remaining_unscaled_source_sample"
                ],
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
