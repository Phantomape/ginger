"""exp-20260701-012: new-settled exit-lifecycle advisory attribution.

Observed-only alpha attribution. This runner refreshes the fixed
exit-lifecycle advisory outcome test from exp-20260623-011 on rows that became
settleable after the prior cutoff date. It changes no entry, ranking, sizing,
exit, live, or paper order behavior.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
EXPERIMENTS_ROOT = QUANT_ROOT / "experiments"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, EXPERIMENTS_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import exp_20260623_011_exit_lifecycle_forward_advisory_outcome as base  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from quant.ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH  # noqa: E402


EXPERIMENT_ID = "exp-20260701-012"
SLUG = "exit_lifecycle_new_settled_advisory_outcome_refresh"
RUNNER = f"quant/experiments/exp_20260701_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260701_012_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SOURCE_DIR = base.SOURCE_DIR
BASELINE_RESULT = base.BASELINE_RESULT

PRIOR_CUTOFF_AS_OF = "2026-06-11"
HYPOTHESIS = (
    "Observed-only alpha: newly settled production exit-lifecycle shadow rows "
    "after 2026-06-11 should preserve the fixed high-urgency/hard-stop next-5d "
    "adverse outcome separation versus no-advisory rows, providing forward "
    "evidence for a future shared exit lifecycle policy without changing exits "
    "today."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "exit_lifecycle_attribution"
TRIAL_FAMILY = "exit_lifecycle_forward_advisory_outcome_attribution"
TRIAL_VARIANT_ID = "post_20260611_new_settled_rows_fixed_bucket_v1"
CHANGED_VARIABLE = "exit_lifecycle_new_settled_shadow_rows_advisory_outcome_refresh_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-011",
    "exp-20260623-016",
    "exp-20260630-020",
]
NEW_EVIDENCE_TYPE = "materially_more_settled_forward_shadow_exit_rows"
NEW_EVIDENCE_AXIS = (
    "Materially more settled forward shadow-exit rows: prior exit-lifecycle "
    "advisory outcome attribution settled as_of dates through 2026-06-11; "
    "current data/exit_lifecycle rows extend to 2026-06-30 and the hot "
    "warehouse can settle fixed 5d outcomes for new post-2026-06-11 rows "
    "without changing buckets, thresholds, horizon, or response curve."
)
CAUSAL_COMPONENTS = [
    "new post-2026-06-11 production exit lifecycle shadow rows",
    "warehouse OHLCV fixed next-open to five-day-close settlement",
    "unchanged advisory severity buckets from exp-20260623-011",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260701-012/exp_20260701_012_exit_lifecycle_new_settled_advisory_outcome_refresh.json",
    "experiments/cards/exp-20260701-012.md",
    "experiments/manifests/exp-20260701-012.json",
    "experiments/tickets/exp-20260701-012.json",
    "experiments/logs/exp-20260701-012.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
CONFIG = {
    **base.CONFIG,
    "prior_cutoff_as_of": PRIOR_CUTOFF_AS_OF,
    "cohort_rule": "as_of_date > prior_cutoff_as_of",
}
DEFAULT_PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "new_rows_reverse_prior_lead",
        "sample_too_small",
        "concentration_failed",
        "advisory_current_loss_label_only",
    ],
    "confidence_reason": (
        "exp-20260623-011/016 found adverse 5d separation on 164 settled rows "
        "through 2026-06-11, but advisory events may simply label positions "
        "already in loss and newer 2026-06-12..2026-06-23 rows can falsify "
        "the lead; no strategy EV/PnL delta is expected because this is "
        "observed-only."
    ),
    "recorded_at": "2026-07-01T23:14:12+00:00",
}


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    base.write_json(path, payload)


def write_text(path: Path, text: str) -> None:
    base.write_text(path, text)


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or DEFAULT_PREDICTION


def empty_analysis(reason: str) -> dict[str, Any]:
    analysis = base.analyze([])
    analysis["failed_reasons"] = [reason]
    analysis["observed_only_lead"] = False
    return analysis


def rows_after_cutoff(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("as_of_date") or "") > PRIOR_CUTOFF_AS_OF]


def rows_through_cutoff(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("as_of_date") or "") <= PRIOR_CUTOFF_AS_OF]


def cohort_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "ticker_count": len({row["ticker"] for row in rows}),
        "as_of_start": min((row["as_of_date"] for row in rows), default=None),
        "as_of_end": max((row["as_of_date"] for row in rows), default=None),
        "entry_start": min((row.get("entry_date") for row in rows if row.get("entry_date")), default=None),
        "entry_end": max((row.get("entry_date") for row in rows if row.get("entry_date")), default=None),
        "exit_start": min((row.get("exit_date") for row in rows if row.get("exit_date")), default=None),
        "exit_end": max((row.get("exit_date") for row in rows if row.get("exit_date")), default=None),
        "advisory_rows": sum(1 for row in rows if row.get("advisory_severity", 0) > 0),
        "hard_stop_rows": sum(1 for row in rows if row.get("advisory_bucket") == "hard_stop"),
    }


def analyze_or_empty(rows: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    return base.analyze(rows) if rows else empty_analysis(reason)


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    mode_map = {
        "new_rows_reverse_prior_lead": {
            "severity_return_spearman_not_negative",
            "severity_spy_replacement_spearman_not_negative",
            "high_urgency_mean_not_worse_than_none",
            "hard_stop_mean_not_worse_than_none",
            "too_few_dates_with_advisory_worse_than_none",
        },
        "sample_too_small": {
            "settled_sample_too_small",
            "advisory_sample_too_small",
            "hard_stop_sample_too_small",
            "no_new_settled_rows_after_prior_cutoff",
        },
        "concentration_failed": {"adverse_pnl_concentration_too_high"},
        "advisory_current_loss_label_only": {
            "high_urgency_median_not_worse_than_none",
            "hard_stop_median_not_worse_than_none",
            "too_few_dates_with_advisory_worse_than_none",
        },
    }
    hit_modes = [
        mode for mode in predicted_modes if mode_map.get(mode, set()).intersection(failed)
    ]
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": bool(success),
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": predicted_modes,
        "failed_reasons": failed,
        "predicted_failure_modes_hit": hit_modes,
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = base.load_baseline_metrics()
    source_rows, source_audit = base.load_exit_lifecycle_rows()
    settled_rows, settlement_audit = base.settle_rows(source_rows)
    new_source_rows = rows_after_cutoff(source_rows)
    prior_source_rows = rows_through_cutoff(source_rows)
    new_settled_rows = rows_after_cutoff(settled_rows)
    prior_settled_rows = rows_through_cutoff(settled_rows)

    new_analysis = analyze_or_empty(new_settled_rows, "no_new_settled_rows_after_prior_cutoff")
    prior_analysis = analyze_or_empty(prior_settled_rows, "no_prior_settled_rows_before_cutoff")
    all_analysis = analyze_or_empty(settled_rows, "settled_sample_too_small")

    observed_lead = bool(new_analysis["observed_only_lead"])
    failed = list(new_analysis["failed_reasons"])
    status = "observed_only_positive_lead" if observed_lead else "rejected"
    decision = (
        "observed_only_exit_lifecycle_new_settled_advisory_loss_lead_not_promoted"
        if observed_lead
        else "rejected_exit_lifecycle_new_settled_advisory_edge_not_persistent"
    )
    why = (
        "The post-cutoff settled cohort preserved the fixed advisory severity "
        "loss separation from the earlier shadow rows. This remains "
        "diagnostic-only because no shared default-off lifecycle helper, "
        "slot-reuse accounting, or executable exit policy was tested."
        if observed_lead
        else "The post-cutoff settled cohort did not preserve the fixed "
        "advisory severity loss separation strongly enough to promote an "
        "exit/risk policy. The prior lead should be treated as unconfirmed "
        "until materially more settled rows arrive or a shared default-off "
        "helper produces fresh evidence."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": base.utc_now(),
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_lead,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new accepted this with a materially-more-settled-forward-rows override.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "prior_cutoff_as_of": PRIOR_CUTOFF_AS_OF,
                "important_boundary": (
                    "This keeps the same buckets, horizon, thresholds, and "
                    "response curve as exp-20260623-011; the only tested "
                    "decision hypothesis is whether newly settled shadow rows "
                    "preserve the advisory outcome lead."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: classify new production "
                "exit-lifecycle rows by unchanged advisory severity and settle "
                "fixed next-5-trading-day outcomes from the warehouse."
            ),
            "4_success_failure_standard": CONFIG,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_dir": repo_rel(SOURCE_DIR),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "warehouse_path": repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
            "prior_cutoff_as_of": PRIOR_CUTOFF_AS_OF,
            "config": CONFIG,
            "outcome_definition": (
                "Gross diagnostic return from next trading session open after "
                "as_of_date to the close five trading days later; no order is "
                "scheduled and no execution cost is applied."
            ),
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(new_source_rows)
            and bool(new_settled_rows)
            and all(bool(row.get("entry_date")) for row in new_settled_rows),
            "fields_checked": [
                "as_of_date",
                "ticker",
                "entry_date",
                "target_price",
                "market_value_usd",
                "advisory_events.event_type",
                "has_advisory_event",
                "forward_5d_return_pct",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "entry_date_present_count": sum(1 for row in new_settled_rows if row.get("entry_date")),
            "target_price_present_count": sum(1 for row in new_source_rows if row.get("target_price") is not None),
            "target_price_relevance": (
                "Checked for Gate 2. It is not consumed by this attribution "
                "and no target exit is scheduled."
            ),
            "source_audit": source_audit,
            "settlement_audit": settlement_audit,
            "cohort_audit": {
                "new_source": cohort_audit(new_source_rows),
                "new_settled": cohort_audit(new_settled_rows),
                "prior_source": cohort_audit(prior_source_rows),
                "prior_settled": cohort_audit(prior_settled_rows),
            },
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": len(new_source_rows),
            "signals_survived": len(new_settled_rows),
            "survival_rate": round(len(new_settled_rows) / len(new_source_rows), 4)
            if new_source_rows
            else None,
            "all_source_rows": source_audit["source_rows"],
            "all_settled_rows": settlement_audit["settled_rows"],
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": {
            "observed_only_lead": observed_lead,
            "failed_reasons": failed,
            "acceptance_checks": new_analysis["acceptance_checks"],
            "decision": decision,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "lead_limitations": [
                "Forward-only daily production rows, not canonical fixed-window PIT replay.",
                "No shared helper, adapter, daily execution rule, or exit policy was promoted.",
                "Outcome is gross diagnostic next-open-to-5d-close path attribution.",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "source_audit": source_audit,
            "settlement_audit": settlement_audit,
            "cohort_counts": {
                "new_source": cohort_audit(new_source_rows),
                "new_settled": cohort_audit(new_settled_rows),
                "prior_source": cohort_audit(prior_source_rows),
                "prior_settled": cohort_audit(prior_settled_rows),
                "all_settled": cohort_audit(settled_rows),
            },
            "new_settled_analysis": new_analysis,
            "prior_settled_analysis": prior_analysis,
            "all_settled_analysis": all_analysis,
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "shared_helper_promoted": False,
            "daily_snapshot_exposed": False,
            "uses_exit_lifecycle_shadow_log": True,
            "live_realistic_execution_envelope": (
                "Not evaluated for live use; this is observed-only attribution "
                "and cannot become live-ready."
            ),
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "realized_failure_mode": ",".join(failed) if failed else "none",
            "forbidden_near_neighbor_retry": (
                "Do not re-slice this same post-2026-06-11 cohort by adjacent "
                "exit lifecycle labels, urgency wording, target, trailing-stop, "
                "time-stop, MFE/giveback, or response-function retunes. A valid "
                "retry needs materially more settled rows, a new row-producing "
                "source/gate shape, or a predeclared shared default-off lifecycle "
                "helper with fresh forward evidence."
            ),
            "new_evidence_required": (
                "More closed production exit-lifecycle rows beyond this cohort, "
                "slot-reuse/winner-collateral accounting, and a shared default-off "
                "advisory lifecycle helper before any Gate 1-4 exit-policy promotion."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(SOURCE_DIR),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260623-011.json",
            "experiments/logs/exp-20260623-016.json",
            "experiments/logs/exp-20260630-020.json",
        ],
    }


def compact_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "all_settled_rows": analysis["all_settled_rows"],
        "bucket_summary": analysis["bucket_summary"],
        "acceptance_checks": analysis["acceptance_checks"],
        "failed_reasons": analysis["failed_reasons"],
        "observed_only_lead": analysis["observed_only_lead"],
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": {
            **payload["gate2"],
            "source_audit": {
                **payload["gate2"]["source_audit"],
                "skipped_rows": payload["gate2"]["source_audit"]["skipped_rows"][:20],
            },
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "cohort_counts": payload["attribution"]["cohort_counts"],
            "new_settled_analysis": compact_analysis(payload["attribution"]["new_settled_analysis"]),
            "prior_settled_analysis": compact_analysis(payload["attribution"]["prior_settled_analysis"]),
            "all_settled_analysis": compact_analysis(payload["attribution"]["all_settled_analysis"]),
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def money(value: Any) -> str:
    number = base.as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def pct(value: Any) -> str:
    number = base.as_float(value)
    return "n/a" if number is None else f"{number:.2%}"


def bucket_table(analysis: dict[str, Any]) -> list[str]:
    rows = [
        "| Advisory Bucket | Rows | Mean Return | Median Return | Mean PnL | Mean vs SPY | Mean vs QQQ |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in base.BUCKETS:
        item = analysis["bucket_summary"][bucket]
        rows.append(
            "| {bucket} | {n} | {mean_ret} | {median_ret} | {mean_pnl} | {spy} | {qqq} |".format(
                bucket=bucket,
                n=item["n"],
                mean_ret=pct(item["mean_forward_5d_return_pct"]),
                median_ret=pct(item["median_forward_5d_return_pct"]),
                mean_pnl=money(item["mean_forward_5d_pnl_usd"]),
                spy=money(item["mean_replacement_value_vs_spy_usd"]),
                qqq=money(item["mean_replacement_value_vs_qqq_usd"]),
            )
        )
    return rows


def build_card(payload: dict[str, Any]) -> str:
    new_analysis = payload["attribution"]["new_settled_analysis"]
    prior_analysis = payload["attribution"]["prior_settled_analysis"]
    counts = payload["attribution"]["cohort_counts"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: exit-lifecycle new-settled advisory outcome refresh",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            f"- New settled cohort: `{counts['new_settled']['rows']}` rows from `{counts['new_settled']['as_of_start']}` to `{counts['new_settled']['as_of_end']}`",
            "",
            "## New Settled Cohort",
            "",
            *bucket_table(new_analysis),
            "",
            "- Severity Spearman(return): `{}`".format(
                new_analysis["acceptance_checks"].get("severity_spearman_return")
            ),
            "- Severity Spearman(SPY replacement): `{}`".format(
                new_analysis["acceptance_checks"].get("severity_spearman_spy_replacement")
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Prior Sanity View",
            "",
            *bucket_table(prior_analysis),
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": base.sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": base.utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    checks = payload["gate4"]["acceptance_checks"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "new_source_rows": payload["attribution"]["cohort_counts"]["new_source"]["rows"],
                "new_settled_rows": checks.get("settled_rows"),
                "new_advisory_rows": checks.get("advisory_rows"),
                "new_hard_stop_rows": checks.get("hard_stop_rows"),
                "severity_spearman_return": checks.get("severity_spearman_return"),
                "severity_spearman_spy_replacement": checks.get("severity_spearman_spy_replacement"),
                "bucket_summary": payload["attribution"]["new_settled_analysis"]["bucket_summary"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
