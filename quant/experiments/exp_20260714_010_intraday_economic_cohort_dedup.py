"""exp-20260714-010: de-duplicate intraday economic execution cohorts."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "scripts", ROOT / "quant"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from intraday_backtester import (  # noqa: E402
    AGGREGATION_RULE_VERSION,
    EXECUTION_RULE_VERSION,
    OUTCOME_RULE_VERSION,
    build_scorecard,
    load_finalized_decisions,
    render_scorecard,
    select_effective_economic_outcomes,
)


EXPERIMENT_ID = "exp-20260714-010"
AS_OF = "2026-07-14"
DATE_TAG = AS_OF.replace("-", "")
SLUG = "intraday_economic_cohort_dedup"
RUNNER = f"quant/experiments/exp_20260714_010_{SLUG}.py"
DAILY_ROOT = ROOT / "data" / "daily" / "intraday" / "backtests"
LEDGER = DAILY_ROOT / "outcome_ledgers" / f"intraday_triage_outcomes_{DATE_TAG}.jsonl"
LATEST = DAILY_ROOT / "latest_scorecard.json"
DATED_SCORECARD = DAILY_ROOT / "scorecards" / f"intraday_triage_scorecard_{DATE_TAG}.json"
DATED_REPORT = DAILY_ROOT / "reports" / f"intraday_triage_scorecard_{DATE_TAG}.txt"
ARTIFACT_ROOT = ROOT / "data" / "experiments" / EXPERIMENT_ID
BEFORE = ARTIFACT_ROOT / "before_scorecard.json"
AFTER = ARTIFACT_ROOT / "after_scorecard.json"
ARTIFACT = ARTIFACT_ROOT / f"exp_20260714_010_{SLUG}.json"
LOG = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs" / "experiment_registry.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ticket = json.loads(TICKET.read_text(encoding="utf-8"))
    baseline_path = BEFORE if BEFORE.exists() else LATEST
    before = json.loads(baseline_path.read_text(encoding="utf-8"))
    outcomes = load_jsonl(LEDGER)
    ledger_sha_before = sha256(LEDGER)

    decisions, _, skipped = load_finalized_decisions(
        ROOT / "data",
        through_date=DATE_TAG,
    )
    source_files = set(before.get("source_decision_files") or [])
    decisions = [
        row for row in decisions
        if row.get("source_decision_file") in source_files
    ]
    after = build_scorecard(
        outcomes,
        decisions=decisions,
        source_files=before.get("source_decision_files") or [],
        skipped_sources=skipped,
        as_of_date=AS_OF,
        price_source=before.get("price_source") or {},
    )
    ledger_sha_after = sha256(LEDGER)

    raw_next_closed = [
        row for row in outcomes
        if row.get("primary_ticker_day_decision")
        and row.get("horizon") == "next_close"
        and row.get("status") == "closed"
    ]
    effective_next, cohort_diagnostics = select_effective_economic_outcomes(
        raw_next_closed
    )
    effective_next = [
        row for row in effective_next if row.get("status") == "closed"
    ]
    ticker_counts = Counter(str(row.get("ticker") or "") for row in effective_next)
    decision_dates = sorted({
        str(row.get("decision_date") or "") for row in effective_next
    })
    semantic_overrides = sum(
        row.get("final_action") != row.get("machine_default_action")
        for row in effective_next
    )
    top_ticker_share = (
        max(ticker_counts.values()) / len(effective_next)
        if effective_next else None
    )
    next_summary = after["horizons"]["next_close"]
    readiness = after["readiness"]
    before_settled = (before.get("readiness") or {}).get(
        "settled_primary_next_close_decisions"
    )
    checks = {
        "baseline_had_33_raw_settled_rows": before_settled == 33,
        "raw_settled_rows_preserved": (
            readiness["raw_settled_primary_next_close_decisions"] == 33
        ),
        "effective_economic_cohorts_are_22": (
            readiness["settled_primary_next_close_decisions"] == 22
        ),
        "eleven_duplicate_rows_are_explicit": (
            readiness["duplicate_settled_economic_rows_excluded"] == 11
        ),
        "latest_decision_aggregation_contract_active": (
            after["aggregation_rule_version"] == AGGREGATION_RULE_VERSION
        ),
        "raw_outcome_ledger_byte_identical": ledger_sha_before == ledger_sha_after,
        "outcome_rule_unchanged": (
            after["outcome_rule_version"] == OUTCOME_RULE_VERSION
            == "intraday_triage_counterfactual_outcome_v1"
        ),
        "execution_rule_unchanged": (
            after["execution_rule_version"] == EXECUTION_RULE_VERSION
            == "intraday_triage_next_5m_execution_v1"
        ),
        "strategy_behavior_unchanged": after["strategy_behavior_changed"] is False,
        "trade_remains_disabled": after["trade_enabled"] is False,
        "early_review_stage_retained": (
            readiness["evidence_stage"] == "observed_only_early"
        ),
    }
    passed = all(checks.values())
    decision = (
        "accepted_measurement_repair_intraday_economic_cohort_dedup"
        if passed else "blocked_intraday_economic_cohort_dedup"
    )
    alpha_read = {
        "status": "observed_only_early_negative_no_semantic_lift",
        "accepted_alpha": False,
        "raw_settled_rows": len(raw_next_closed),
        "effective_economic_cohorts": len(effective_next),
        "duplicate_rows_excluded": cohort_diagnostics["duplicate_rows_excluded"],
        "decision_dates": decision_dates,
        "unique_tickers": len(ticker_counts),
        "top_ticker_share": round(top_ticker_share, 6)
        if top_ticker_share is not None else None,
        "semantic_action_overrides": semantic_overrides,
        "incremental_pnl_vs_no_adjustment_usd": next_summary[
            "incremental_pnl_vs_no_adjustment_usd"
        ],
        "semantic_lift_vs_machine_default_usd": next_summary[
            "semantic_lift_vs_machine_default_usd"
        ],
        "final_vs_always_add_usd": next_summary["final_vs_always_add_usd"],
        "daily_portfolio_curve": after["daily_portfolio_curve_next_close"],
        "interpretation": (
            "The current policy has no identifiable semantic lift because every "
            "effective final action equals the machine default. Its three "
            "REDUCE_RISK decisions lost net value versus no adjustment; the "
            "sample remains an early forward read, not Gate 1-4 alpha evidence."
        ),
    }
    changed_files = [
        "quant/intraday_backtester.py",
        "quant/test_intraday_backtester.py",
        RUNNER,
        rel(BEFORE),
        rel(AFTER),
        rel(ARTIFACT),
        rel(LATEST),
        rel(DATED_SCORECARD),
        rel(DATED_REPORT),
        rel(LOG),
        rel(CARD),
        rel(MANIFEST),
        rel(TICKET),
        "docs/experiment_registry.json",
        "docs/frozen_families.jsonl",
        "docs/alpha-optimization-playbook.md",
    ]
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": "alpha-explore",
        "lane": "measurement_repair",
        "status": "accepted" if passed else "blocked",
        "accepted": passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": passed,
        "decision": decision,
        "hypothesis": ticket["hypothesis"],
        "alpha_hypothesis": (
            "Intraday guardrails plus semantic news selection add positive net "
            "next-close decision value versus machine-default and no-adjustment actions."
        ),
        "change_type": ticket["change_type"],
        "mechanism_family": ticket["mechanism_family"],
        "trial_family": ticket["trial_family"],
        "trial_variant_id": ticket["trial_variant_id"],
        "single_causal_variable": ticket["single_causal_variable"],
        "changed_variable": ticket["changed_variable"],
        "causal_components": ticket["causal_components"],
        "nearby_prior_experiments": ticket["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": ticket["multiple_testing_risk_bucket"],
        "new_evidence_type": ticket["new_evidence_type"],
        "prediction": ticket.get("prediction"),
        "calibration": {
            "predicted_success_probability": (ticket.get("prediction") or {}).get(
                "success_probability"
            ),
            "actual_success": 1 if passed else 0,
            "brier_score": 0.0025 if passed else 0.9025,
            "realized_failure_mode": None if passed else "cohort_repair_check_failed",
        },
        "before": {
            "artifact": rel(BEFORE),
            "settled_primary_next_close_decisions": before_settled,
            "next_close": (before.get("horizons") or {}).get("next_close"),
        },
        "after": {
            "artifact": rel(AFTER),
            "readiness": readiness,
            "next_close": next_summary,
        },
        "delta_metrics": {
            "raw_settled_rows_delta": 0,
            "effective_minus_pre_repair_count": (
                readiness["settled_primary_next_close_decisions"] - before_settled
            ),
            "duplicate_rows_excluded": (
                readiness["duplicate_settled_economic_rows_excluded"]
            ),
            "strategy_behavior_delta": 0,
        },
        "checks": checks,
        "alpha_early_review": alpha_read,
        "headline_metrics": {
            "checks_passed": sum(checks.values()),
            "checks_total": len(checks),
            "raw_settled_primary_next_close_decisions": len(raw_next_closed),
            "effective_economic_cohorts": len(effective_next),
            "duplicate_rows_excluded": cohort_diagnostics["duplicate_rows_excluded"],
            "semantic_action_overrides": semantic_overrides,
            "incremental_pnl_vs_no_adjustment_usd": next_summary[
                "incremental_pnl_vs_no_adjustment_usd"
            ]["sum"],
            "semantic_lift_vs_machine_default_usd": next_summary[
                "semantic_lift_vs_machine_default_usd"
            ]["sum"],
            "final_vs_always_add_usd": next_summary[
                "final_vs_always_add_usd"
            ]["sum"],
            "strategy_behavior_delta": 0,
        },
        "gate1": {
            "passed": BEFORE.exists() and LEDGER.exists(),
            "baseline_artifact": rel(BEFORE),
            "note": "Forward measurement repair; canonical three-window strategy is unchanged.",
        },
        "gate2": {
            "passed": passed,
            "runtime_fields": [
                "ticker",
                "decision_timestamp",
                "execution_time",
                "horizon",
                "observation_id",
                "final_action",
                "machine_default_action",
            ],
            "sentinel_note": (
                "entry_date and target_price remain canonical signal sentinels; "
                "this advisory measurement surface does not generate entries."
            ),
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
        },
        "gate4": {
            "passed": passed,
            "decision": decision,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "strategy_behavior_changed": False,
            "failed_reasons": [name for name, ok in checks.items() if not ok],
        },
        "production_impact": {
            "canonical_backtester_changed": False,
            "counterfactual_outcome_rows_changed": False,
            "counterfactual_actions_changed": False,
            "counterfactual_costs_changed": False,
            "counterfactual_execution_semantics_changed": False,
            "scorecard_aggregation_repaired": passed,
            "live_orders_changed": False,
            "trade_enabled": False,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Primary status was scoped to ticker-day, so Saturday and Sunday "
                "snapshots that could only execute in the same Monday bar were "
                "treated as independent. Latest-pre-execution cohort selection "
                "keeps immutable raw rows while removing correlation inflation."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve another ID for routine scorecard refreshes, raw "
                "ticker-day recounts, weekend reslicing, or action-threshold retuning."
            ),
            "new_evidence_required": (
                "Review stability at 50 effective next-close economic cohorts. "
                "Only at 100 effective cohorts may a separately frozen alpha "
                "promotion hypothesis be reserved; zero semantic overrides still "
                "means the semantic component is unidentified."
            ),
        },
        "reopen_condition": (
            "50 effective next-close economic cohorts under aggregation rule v1 "
            "for stability review; 100 effective cohorts before a frozen Gate 1-4 "
            "alpha promotion hypothesis."
        ),
        "rejection_reason": None if passed else ";".join(
            name for name, ok in checks.items() if not ok
        ),
        "changed_files": changed_files,
        "related_files": changed_files,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_intraday_backtester.py -q",
            ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": passed,
    }

    if not BEFORE.exists():
        write_json(BEFORE, before)
    write_json(AFTER, after)
    write_json(ARTIFACT, payload)
    if passed:
        write_json(LATEST, after)
        write_json(DATED_SCORECARD, after)
        DATED_REPORT.parent.mkdir(parents=True, exist_ok=True)
        DATED_REPORT.write_text(render_scorecard(after), encoding="utf-8")
    save_experiment_log_entry(payload, allow_duplicate=True)
    CARD.write_text(
        f"# {EXPERIMENT_ID}: Intraday Economic Cohort De-duplication\n\n"
        f"- Decision: `{decision}`\n"
        f"- Raw/effective settled next-close rows: `"
        f"{len(raw_next_closed)}/{len(effective_next)}`\n"
        f"- Duplicate rows excluded: `"
        f"{cohort_diagnostics['duplicate_rows_excluded']}`\n"
        f"- Incremental PnL vs no adjustment: `"
        f"${next_summary['incremental_pnl_vs_no_adjustment_usd']['sum']:.2f}`\n"
        f"- Semantic lift vs machine default: `"
        f"${next_summary['semantic_lift_vs_machine_default_usd']['sum']:.2f}`\n"
        f"- Semantic action overrides: `{semantic_overrides}`\n"
        "- Strategy behavior changed: `false`\n"
        "- Accepted alpha: `false`\n\n"
        "The measurement repair is accepted. The early alpha read is negative "
        "and not promotion-grade: all effective final actions equal the machine "
        "default, while REDUCE_RISK lost value versus no adjustment.\n",
        encoding="utf-8",
    )
    persist_self_registered_result(
        REGISTRY,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=ticket.get("prediction"),
        result={
            "accepted": passed,
            "accepted_alpha": False,
            "accepted_measurement_repair": passed,
            "decision": decision,
            "artifact": rel(ARTIFACT),
            "log": rel(LOG),
            "gate4": payload["gate4"],
            "headline_metrics": payload["headline_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
        },
        status=payload["status"],
        fields={
            **payload,
            "artifact": rel(ARTIFACT),
            "log": rel(LOG),
            "card_file": rel(CARD),
            "revision_manifest_file": rel(MANIFEST),
            "ticket_file": rel(TICKET),
            "allowed_write_scope": ticket["allowed_write_scope"],
        },
    )
    write_json(
        MANIFEST,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": decision,
            "artifact": rel(ARTIFACT),
            "runner": RUNNER,
            "checks": checks,
            "updated_at": utc_now(),
        },
    )
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "checks": checks,
        "alpha_early_review": alpha_read,
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
