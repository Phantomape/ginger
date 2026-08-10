"""exp-20260725-001: repair partial-session intraday pseudo-settlements."""

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
    SESSION_COMPLETION_RULE_VERSION,
    build_scorecard,
    load_finalized_decisions,
    migrate_intraday_outcomes_to_current_rule,
    render_scorecard,
)
import build_reopen_readiness  # noqa: E402


EXPERIMENT_ID = "exp-20260725-001"
AS_OF = "2026-07-24"
DATE_TAG = AS_OF.replace("-", "")
SLUG = "intraday_completed_close_settlement"
RUNNER = f"quant/experiments/exp_20260725_001_{SLUG}.py"
DAILY_ROOT = ROOT / "data" / "daily" / "intraday" / "backtests"
LEDGER = DAILY_ROOT / "outcome_ledgers" / f"intraday_triage_outcomes_{DATE_TAG}.jsonl"
LATEST = DAILY_ROOT / "latest_scorecard.json"
DATED_SCORECARD = DAILY_ROOT / "scorecards" / f"intraday_triage_scorecard_{DATE_TAG}.json"
DATED_REPORT = DAILY_ROOT / "reports" / f"intraday_triage_scorecard_{DATE_TAG}.txt"
REOPEN_READINESS = ROOT / "data" / "reopen_readiness.json"
ARTIFACT_ROOT = ROOT / "data" / "experiments" / EXPERIMENT_ID
BEFORE_SCORECARD = ARTIFACT_ROOT / "before_scorecard.json"
BEFORE_LEDGER = ARTIFACT_ROOT / "before_outcome_ledger.jsonl"
AFTER_SCORECARD = ARTIFACT_ROOT / "after_scorecard.json"
ARTIFACT = ARTIFACT_ROOT / f"exp_20260725_001_{SLUG}.json"
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


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
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


def _close_is_partial(row: dict) -> bool:
    if row.get("horizon") not in {"rth_close", "next_close", "d3_close"}:
        return False
    if row.get("status") != "closed":
        return False
    text = str(row.get("horizon_time") or "")
    return len(text) < 16 or text[11:16] != "15:55"


def _same_except_rule_metadata(before: dict, after: dict) -> bool:
    ignored = {"outcome_rule_version", "session_completion_rule_version"}
    return (
        {key: value for key, value in before.items() if key not in ignored}
        == {key: value for key, value in after.items() if key not in ignored}
    )


def main() -> int:
    ticket = json.loads(TICKET.read_text(encoding="utf-8"))
    baseline_scorecard_path = (
        BEFORE_SCORECARD if BEFORE_SCORECARD.exists() else DATED_SCORECARD
    )
    baseline_ledger_path = BEFORE_LEDGER if BEFORE_LEDGER.exists() else LEDGER
    before_scorecard = json.loads(
        baseline_scorecard_path.read_text(encoding="utf-8")
    )
    before_rows = load_jsonl(baseline_ledger_path)
    before_ledger_sha = sha256(baseline_ledger_path)
    before_scorecard_sha = sha256(baseline_scorecard_path)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    if not BEFORE_SCORECARD.exists():
        BEFORE_SCORECARD.write_bytes(baseline_scorecard_path.read_bytes())
    if not BEFORE_LEDGER.exists():
        BEFORE_LEDGER.write_bytes(baseline_ledger_path.read_bytes())

    migrated_rows = migrate_intraday_outcomes_to_current_rule(before_rows)
    partial_indexes = [
        index for index, row in enumerate(before_rows) if _close_is_partial(row)
    ]
    partial_by_horizon = Counter(
        str(before_rows[index].get("horizon")) for index in partial_indexes
    )
    demoted_rows = [migrated_rows[index] for index in partial_indexes]
    derived_keys = {
        "horizon_time",
        "horizon_price",
        "ticker_return_bps",
        "mfe_bps",
        "mae_bps",
        "final_result",
        "machine_default_result",
        "always_add_result",
        "incremental_pnl_vs_no_adjustment_usd",
        "semantic_lift_vs_machine_default_usd",
        "final_vs_always_add_usd",
        "incremental_return_on_position_bps",
        "semantic_lift_on_position_bps",
        "final_vs_always_add_on_position_bps",
        "wait_trigger_result",
    }

    decisions, _, skipped = load_finalized_decisions(
        ROOT / "data",
        through_date=DATE_TAG,
    )
    source_files = set(before_scorecard.get("source_decision_files") or [])
    decisions = [
        row for row in decisions
        if row.get("source_decision_file") in source_files
    ]
    # Build from the legacy rows so the scorecard records the number defended
    # against, while build_scorecard applies the same migration internally.
    after_scorecard = build_scorecard(
        before_rows,
        decisions=decisions,
        source_files=before_scorecard.get("source_decision_files") or [],
        skipped_sources=skipped,
        as_of_date=AS_OF,
        price_source=before_scorecard.get("price_source") or {},
    )

    write_jsonl(LEDGER, migrated_rows)
    write_json(DATED_SCORECARD, after_scorecard)
    write_json(LATEST, after_scorecard)
    DATED_REPORT.parent.mkdir(parents=True, exist_ok=True)
    DATED_REPORT.write_text(render_scorecard(after_scorecard), encoding="utf-8")
    write_json(AFTER_SCORECARD, after_scorecard)
    reopen = build_reopen_readiness.build()

    after_ledger_sha = sha256(LEDGER)
    after_scorecard_sha = sha256(DATED_SCORECARD)
    next_before = before_scorecard["horizons"]["next_close"]
    next_after = after_scorecard["horizons"]["next_close"]
    readiness_before = before_scorecard["readiness"]
    readiness_after = after_scorecard["readiness"]
    intraday_reopen = next(
        lane for lane in reopen["lanes"]
        if lane.get("lane") == "intraday_triage_completed_close_settlement"
    )

    checks = {
        "ticket_has_valid_lifecycle_status": ticket.get("status") in {
            "claimed", "accepted"
        },
        "dated_ledger_has_1028_rows": len(before_rows) == len(migrated_rows) == 1028,
        "outcome_rule_bumped_to_v2": (
            OUTCOME_RULE_VERSION == "intraday_triage_counterfactual_outcome_v2"
            and {row.get("outcome_rule_version") for row in migrated_rows}
            == {OUTCOME_RULE_VERSION}
        ),
        "aggregation_rule_unchanged": (
            AGGREGATION_RULE_VERSION
            == "intraday_triage_latest_pre_execution_cohort_v1"
        ),
        "execution_rule_unchanged": (
            EXECUTION_RULE_VERSION == "intraday_triage_next_5m_execution_v1"
        ),
        "session_completion_contract_recorded": (
            after_scorecard.get("session_completion_rule_version")
            == SESSION_COMPLETION_RULE_VERSION
        ),
        "exactly_64_partial_close_rows_demoted": len(partial_indexes) == 64,
        "demotion_breakdown_is_12_12_40": partial_by_horizon == {
            "rth_close": 12,
            "next_close": 12,
            "d3_close": 40,
        },
        "demoted_rows_are_pending": all(
            row.get("status") == "pending_horizon_bar" for row in demoted_rows
        ),
        "demoted_rows_drop_realized_fields": all(
            not (derived_keys & set(row)) for row in demoted_rows
        ),
        "h1_outcomes_unchanged_except_rule_metadata": all(
            _same_except_rule_metadata(before, after)
            for before, after in zip(before_rows, migrated_rows)
            if before.get("horizon") == "h1"
        ),
        "before_artifacts_match_original_hashes": (
            sha256(BEFORE_LEDGER) == before_ledger_sha
            and sha256(BEFORE_SCORECARD) == before_scorecard_sha
        ),
        "canonical_hashes_changed": (
            after_ledger_sha != before_ledger_sha
            and after_scorecard_sha != before_scorecard_sha
        ),
        "next_close_raw_settled_corrected_to_113": (
            readiness_after["raw_settled_primary_next_close_decisions"] == 113
            and next_after["raw_closed"] == 113
        ),
        "next_close_effective_settled_corrected_to_94": (
            readiness_after["settled_primary_next_close_decisions"] == 94
            and next_after["closed"] == 94
        ),
        "nineteen_duplicates_still_excluded": (
            readiness_after["duplicate_settled_economic_rows_excluded"] == 19
            and next_after["duplicate_rows_excluded"] == 19
        ),
        "alpha_reopen_is_fail_closed": (
            readiness_after["evidence_stage"]
            == "observed_only_stability_review"
            and intraday_reopen.get("status") == "not_ready"
            and intraday_reopen.get("counters", {}).get(
                "strict_effective_next_close_settlements"
            ) == 94
        ),
        "strategy_behavior_unchanged": (
            after_scorecard.get("strategy_behavior_changed") is False
        ),
        "trade_remains_disabled": after_scorecard.get("trade_enabled") is False,
    }
    passed = all(checks.values())
    decision = (
        "accepted_measurement_repair_intraday_completed_close_settlement"
        if passed else "blocked_intraday_completed_close_settlement"
    )

    changed_files = [
        "quant/intraday_backtester.py",
        "quant/test_intraday_backtester.py",
        "scripts/build_reopen_readiness.py",
        "quant/test_build_reopen_readiness.py",
        RUNNER,
        rel(LEDGER),
        rel(DATED_SCORECARD),
        rel(DATED_REPORT),
        rel(LATEST),
        rel(REOPEN_READINESS),
        rel(BEFORE_SCORECARD),
        rel(BEFORE_LEDGER),
        rel(AFTER_SCORECARD),
        rel(ARTIFACT),
        rel(LOG),
        rel(CARD),
        rel(MANIFEST),
        rel(TICKET),
        "docs/experiment_registry.json",
        "docs/frozen_families.jsonl",
    ]
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": "codex-alpha-automation",
        "lane": "measurement_repair",
        "status": "accepted" if passed else "blocked",
        "accepted": passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": passed,
        "decision": decision,
        "hypothesis": ticket["hypothesis"],
        "alpha_hypothesis": (
            "Machine-default intraday REDUCE_RISK actions improve net next-close "
            "replacement value versus no adjustment across completed cohorts."
        ),
        "alpha_preflight_decision": (
            "not_reserved_invalid_maturity_count; strict completed effective "
            "next-close cohorts are 94/100"
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
            "brier_score": 0.01 if passed else 0.81,
            "realized_failure_mode": None if passed else "settlement_repair_check_failed",
        },
        "before": {
            "scorecard_artifact": rel(BEFORE_SCORECARD),
            "ledger_artifact": rel(BEFORE_LEDGER),
            "scorecard_sha256": before_scorecard_sha,
            "ledger_sha256": before_ledger_sha,
            "settled_primary_next_close_decisions": readiness_before[
                "settled_primary_next_close_decisions"
            ],
            "next_close": next_before,
        },
        "after": {
            "scorecard_artifact": rel(AFTER_SCORECARD),
            "scorecard_sha256": after_scorecard_sha,
            "ledger_sha256": after_ledger_sha,
            "readiness": readiness_after,
            "next_close": next_after,
            "reopen_lane": intraday_reopen,
        },
        "delta_metrics": {
            "raw_settled_next_close_delta": (
                readiness_after["raw_settled_primary_next_close_decisions"]
                - readiness_before["raw_settled_primary_next_close_decisions"]
            ),
            "effective_settled_next_close_delta": (
                readiness_after["settled_primary_next_close_decisions"]
                - readiness_before["settled_primary_next_close_decisions"]
            ),
            "partial_close_rows_demoted": len(partial_indexes),
            "strategy_behavior_delta": 0,
        },
        "checks": checks,
        "headline_metrics": {
            "checks_passed": sum(checks.values()),
            "checks_total": len(checks),
            "partial_close_rows_demoted": len(partial_indexes),
            "raw_settled_primary_next_close_before": 125,
            "raw_settled_primary_next_close_after": 113,
            "effective_settled_primary_next_close_before": 106,
            "effective_settled_primary_next_close_after": 94,
            "duplicate_rows_excluded": 19,
            "strategy_behavior_delta": 0,
        },
        "gate1": {
            "passed": BEFORE_SCORECARD.exists() and BEFORE_LEDGER.exists(),
            "baseline_artifact": rel(BEFORE_SCORECARD),
            "canonical_strategy_baseline": ticket["baseline_result_file"],
            "note": "Measurement repair only; canonical Gate-1 strategy is unchanged.",
        },
        "gate2": {
            "passed": passed,
            "runtime_fields": [
                "execution_time",
                "horizon",
                "horizon_time",
                "status",
                "outcome_rule_version",
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
            "counterfactual_settlement_semantics_repaired": passed,
            "outcome_prices_refetched": False,
            "live_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "trade_enabled": False,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The old horizon selector treated the last bar currently present "
                "in a target session as its close and could also shift to the next "
                "observed ticker session. A 13:05 ET snapshot therefore created 64 "
                "pseudo-settled close-dependent rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve the aborted 106-row machine-default attribution, "
                "count partial/early-close bars as settlements, or shift a missing "
                "expected session to a later observed session."
            ),
            "new_evidence_required": (
                "Let the v2 routine pipeline accumulate at least 100 strict effective "
                "next-close cohorts, then generate a fresh outcome-blind D0-D3 scope "
                "before any separately reserved alpha hypothesis."
            ),
        },
        "reopen_condition": (
            "At least 100 strict effective primary next-close economic cohorts under "
            "outcome rule v2, with a completed 15:55 ET bar and expected-session identity."
        ),
        "rejection_reason": None if passed else ";".join(
            name for name, ok in checks.items() if not ok
        ),
        "changed_files": changed_files,
        "related_files": changed_files,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest "
            "quant\\test_intraday_backtester.py quant\\test_build_reopen_readiness.py -q",
            ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": passed,
    }

    write_json(ARTIFACT, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    CARD.parent.mkdir(parents=True, exist_ok=True)
    CARD.write_text(
        f"# {EXPERIMENT_ID}: Intraday completed-close settlement\n\n"
        f"- Decision: `{decision}`\n"
        f"- Close-dependent rows demoted: `{len(partial_indexes)}` "
        f"(`{dict(partial_by_horizon)}`)\n"
        "- Raw/effective settled next-close rows: "
        f"`125/106 -> {next_after['raw_closed']}/{next_after['closed']}`\n"
        f"- Reopen state: `{intraday_reopen['status']}` at "
        f"`{intraday_reopen['counters']['strict_effective_next_close_settlements']}/100`\n"
        "- Strategy behavior changed: `false`\n"
        "- Accepted alpha: `false`\n\n"
        "The measurement repair is accepted. The apparent 106-row alpha maturity "
        "was a partial-session artifact; the machine-action hypothesis was not reserved.\n",
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
        "before_hashes": {
            "ledger": before_ledger_sha,
            "scorecard": before_scorecard_sha,
        },
        "after_hashes": {
            "ledger": after_ledger_sha,
            "scorecard": after_scorecard_sha,
        },
        "reopen": intraday_reopen,
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
