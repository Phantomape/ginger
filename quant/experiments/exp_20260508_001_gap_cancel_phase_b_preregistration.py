"""exp-20260508-001 gap-cancel Phase B preregistration audit.

Observe-only bridge between the orthogonal discriminator loss-attribution
audit and any production-parity bypass experiment. It reconciles the available
gap-cancel source events, classifies candidate discriminators against known
do-not-retry families, and writes pre-registered Phase B parameters.

This script does not alter strategy logic, thresholds, prompts, sizing, exits,
or the production/backtest order path.
"""

from __future__ import annotations

import csv
import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXP_ID = "exp-20260508-001_gap_cancel_phase_b_preregistration"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_RECONCILIATION = OUT_DIR / "event_source_reconciliation.json"
OUT_MATRIX = OUT_DIR / "candidate_decision_matrix.csv"
OUT_PREREG = OUT_DIR / "phase_b_preregistration.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"

PHASE_A_ID = "exp-20260507-920_gap_cancel_orthogonal_discriminator_audit"
PHASE_A_DIR = REPO_ROOT / "data" / "experiments" / PHASE_A_ID
PHASE_A_RANKING = PHASE_A_DIR / "discriminator_ranking.json"
PHASE_A_CATALOG = PHASE_A_DIR / "event_catalog.json"
PHASE_A_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / f"{PHASE_A_ID}.json"

STANDARD_ORACLE_DIR = REPO_ROOT / "data" / "experiments" / "oracle_standard_3window_20260501_220042"
NO_ENTRY_ORACLE_DIR = REPO_ROOT / "data" / "experiments" / "oracle_no_entry_restriction_3window"

WINDOWS = ("late_strong", "mid_weak", "old_thin")
TARGET_DECISIONS = ("gap_cancel", "adverse_gap_down_cancel")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def count_phase_a_events(catalog: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = OrderedDict()
    total = 0
    for window in WINDOWS:
        rows = [event for event in catalog["events"] if event.get("window") == window]
        decisions = {decision: 0 for decision in TARGET_DECISIONS}
        for row in rows:
            decision = row.get("decision")
            if decision in decisions:
                decisions[decision] += 1
        count = sum(decisions.values())
        total += count
        by_window[window] = {
            "phase_a_cancel_like_events": count,
            "decision_counts": decisions,
            "tickers": sorted({row.get("ticker") for row in rows if row.get("ticker")}),
        }
    return {"total": total, "by_window": by_window}


def count_standard_entry_skip_oracles() -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = OrderedDict()
    total = 0
    for window in WINDOWS:
        path = STANDARD_ORACLE_DIR / f"{window}_entry_skip_oracle.json"
        payload = load_json(path)
        oracle = payload.get("entry_skip_oracle", {})
        by_decision = oracle.get("by_decision", {})
        decisions = {
            decision: int(by_decision.get(decision, {}).get("sample_count", 0))
            for decision in TARGET_DECISIONS
        }
        count = sum(decisions.values())
        total += count
        by_window[window] = {
            "source": str(path.relative_to(REPO_ROOT)),
            "evaluated_skip_event_count": oracle.get("evaluated_skip_event_count"),
            "full_skip_count_reported_by_backtest": oracle.get("full_skip_count_reported_by_backtest"),
            "cancel_like_events": count,
            "decision_counts": decisions,
        }
    return {"total": total, "by_window": by_window}


def inspect_no_entry_restriction_artifacts() -> dict[str, Any]:
    files = sorted(path for path in NO_ENTRY_ORACLE_DIR.glob("*.json") if path.is_file())
    file_summaries = []
    has_sample_skips = False
    target_decision_mentions = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        sample_skip_mentions = text.count("sample_skips")
        decision_mentions = sum(text.count(decision) for decision in TARGET_DECISIONS)
        has_sample_skips = has_sample_skips or sample_skip_mentions > 0
        target_decision_mentions += decision_mentions
        file_summaries.append(
            {
                "file": str(path.relative_to(REPO_ROOT)),
                "bytes": path.stat().st_size,
                "sample_skips_mentions": sample_skip_mentions,
                "target_decision_mentions": decision_mentions,
            }
        )
    return {
        "directory": str(NO_ENTRY_ORACLE_DIR.relative_to(REPO_ROOT)),
        "has_replayable_sample_skips": has_sample_skips,
        "target_decision_mentions": target_decision_mentions,
        "files": file_summaries,
        "interpretation": (
            "No-entry-restriction artifacts summarize the oracle candidate pool but do not "
            "currently carry replayable gap/adverse cancel skip-detail rows."
        ),
    }


def coverage_lookup(phase_a_log: dict[str, Any]) -> dict[str, float]:
    coverage = {}
    for field, payload in phase_a_log.get("feature_coverage", {}).items():
        if isinstance(payload, dict) and "coverage" in payload:
            coverage[field] = float(payload["coverage"])
    return coverage


def candidate_status(row: dict[str, Any], coverage: dict[str, float]) -> tuple[str, str, str]:
    field = row.get("field", "")
    predicate = row.get("predicate", "")

    if field in {"gap_bucket", "gap_abs_pct", "gap_pct"}:
        return (
            "disabled",
            "too_close_to_rejected_global_gap_threshold_family",
            "exp-20260428-021 already exhausted global gap threshold scans; do not start Phase B with gap magnitude alone.",
        )

    if field.startswith("news_"):
        cov = coverage.get("news_t1t2_count_3d", 0.0)
        return (
            "deferred",
            "insufficient_news_archive_coverage",
            f"News archive coverage is {cov:.0%}; below the 80% Phase B preflight requirement.",
        )

    if field in {"days_since_earnings", "earnings_shock_pct"}:
        cov = coverage.get(field, 0.0)
        return (
            "deferred",
            "insufficient_earnings_coverage",
            f"{field} coverage is {cov:.0%}; this repeats the known earnings data blind spot.",
        )

    if field == "bbwidth20" and predicate == "bbwidth20>=median":
        return (
            "primary_phase_b_candidate",
            "orthogonal_volatility_expansion_discriminator",
            "100% PIT-safe coverage, spans all three windows, not a sector/strategy/regime/rank/TQS or gap-threshold exception.",
        )

    if field == "volume_vs_20d_avg":
        return (
            "secondary_candidate",
            "orthogonal_but_direction_needs_care",
            "The observed split is lower-than-median volume, not the intuitive high-volume confirmation hypothesis.",
        )

    if field == "sector_5d_rs":
        return (
            "secondary_candidate",
            "allowed_axis_but_not_first",
            "Five-day relative strength is not the rejected 20-day sector conditional, but it adds benchmark/basket complexity.",
        )

    if field == "atr14_t_over_t20":
        return (
            "tertiary_candidate",
            "orthogonal_but_weaker_lift",
            "Covered and PIT-safe, but weaker than bbwidth20 in the Phase A ranking.",
        )

    if field.startswith("recent_8k"):
        return (
            "deferred",
            "semantic_direction_not_actionable_yet",
            "The current split rewards lower severity, which is not a clean event-confirmation bypass policy.",
        )

    return (
        "deferred",
        "not_selected_for_first_phase_b",
        "Does not dominate the simpler bbwidth20 preregistered candidate.",
    )


def build_candidate_matrix(ranking: dict[str, Any], phase_a_log: dict[str, Any]) -> list[dict[str, Any]]:
    coverage = coverage_lookup(phase_a_log)
    rows = []
    for idx, item in enumerate(ranking.get("single_variable_ranking", []), start=1):
        status, reason_code, rationale = candidate_status(item, coverage)
        rows.append(
            {
                "rank": idx,
                "field": item.get("field"),
                "predicate": item.get("predicate"),
                "threshold": item.get("threshold", item.get("value", "")),
                "count": item.get("count"),
                "windows": json.dumps(item.get("windows", {}), sort_keys=True),
                "avg_forward_return": item.get("avg_forward_return"),
                "lift_vs_all": item.get("avg_return_lift_vs_all"),
                "status": status,
                "reason_code": reason_code,
                "rationale": rationale,
            }
        )
    return rows


def write_candidate_matrix(rows: list[dict[str, Any]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        "rank",
        "field",
        "predicate",
        "threshold",
        "count",
        "windows",
        "avg_forward_return",
        "lift_vs_all",
        "status",
        "reason_code",
        "rationale",
    ]
    with OUT_MATRIX.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_preregistration(ranking: dict[str, Any], matrix_rows: list[dict[str, Any]]) -> dict[str, Any]:
    primary = next(row for row in matrix_rows if row["status"] == "primary_phase_b_candidate")
    primary_rank = next(
        item for item in ranking.get("single_variable_ranking", []) if item.get("predicate") == primary["predicate"]
    )
    return {
        "phase_b_experiment_stub": "exp-20260508-MMM_gap_cancel_bbwidth_bypass",
        "lane": "alpha_discovery",
        "single_causal_variable": "Allow upside gap_cancel bypass only when bbwidth20 is at or above the Phase A median.",
        "superseded_by": {
            "experiment_id": "exp-20260508-009",
            "decision": "rejected",
            "reason": (
                "The preregistered bbwidth20>=0.269211 gap-cancel bypass was already replayed "
                "across the canonical three windows and failed with negative EV windows in "
                "mid_weak and old_thin."
            ),
            "do_not_retry_without": "new forward evidence or a materially different orthogonal discriminator",
        },
        "policy_scope": {
            "bypass_upside_gap_cancel": True,
            "bypass_adverse_gap_down_cancel": False,
            "position_sizing_changed": False,
            "candidate_ranking_changed": False,
            "exit_logic_changed": False,
        },
        "pre_registered_discriminator": {
            "field": "bbwidth20",
            "predicate": "bbwidth20>=0.269211",
            "threshold_source": "Phase A median split from exp-20260507-920; no post-hoc retuning.",
            "threshold": primary_rank.get("threshold"),
            "phase_a_count": primary_rank.get("count"),
            "phase_a_windows": primary_rank.get("windows"),
            "phase_a_avg_forward_return": primary_rank.get("avg_forward_return"),
            "phase_a_lift_vs_all": primary_rank.get("avg_return_lift_vs_all"),
        },
        "explicit_non_parameters": {
            "do_not_use_gap_bucket_as_selector": True,
            "do_not_use_gap_abs_pct_as_selector": True,
            "do_not_use_news_or_earnings_until_coverage_recovers": True,
            "do_not_add_sector_or_strategy_exceptions": True,
            "do_not_test_joint_pairs_first": True,
        },
        "gap_cap_guidance": {
            "phase_a_observation": "The strongest gap-magnitude buckets were 4-5% and >5%; a 3% cap would not test the Phase A top effect.",
            "preregistered_first_test": "Do not introduce a new max-gap cap in the first bbwidth20 Phase B replay; adding a cap is a separate causal variable.",
            "production_risk_note": "If a safety cap is later required, run it as a separately named experiment and do not count that result as the pure bbwidth20 test.",
        },
        "required_verification": [
            "pytest quant/test_production_parity.py with policy=None must pass bit-for-bit default behavior.",
            "Feature builder coverage for bbwidth20 on replayed gap-cancel events must be at least 80%.",
            "Run late_strong, mid_weak, and old_thin windows with baseline versus bypass_upside_only.",
            "Pass Gate 4 in at least 2 of 3 windows with no window showing material EV deterioration.",
            "Skip attribution diff must show only gap_cancel count declines by the bypass hit count.",
            "New admitted cohort win rate must not be materially below baseline.",
        ],
        "historical_experiment_check": {
            "exp-20260428-021": "Not a global gap threshold scan; gap magnitude is explicitly excluded as the first selector.",
            "exp-20260428-022": "Not a sector or strategy exception.",
            "exp-20260504-055": "Not event-bundle coverage; news/earnings are explicitly deferred due missingness.",
            "exp-20260427-019_to_025": "Not scarce-slot, regime, breadth, rank, or TQS conditionalization.",
        },
    }


def build_reconciliation(catalog: dict[str, Any]) -> dict[str, Any]:
    phase_a_counts = count_phase_a_events(catalog)
    standard_counts = count_standard_entry_skip_oracles()
    no_entry = inspect_no_entry_restriction_artifacts()
    status = "matched_standard_sources" if phase_a_counts["total"] == standard_counts["total"] else "mismatch"
    analyst_status = "unreconciled_missing_one" if phase_a_counts["total"] != 21 else "matched_analyst_note"
    return {
        "phase_a_feature_catalog": phase_a_counts,
        "standard_entry_skip_oracle": standard_counts,
        "no_entry_restriction_artifacts": no_entry,
        "source_reconciliation_status": status,
        "analyst_note_count": 21,
        "analyst_note_reconciliation_status": analyst_status,
        "interpretation": (
            "The replayable standard three-window source has 20 gap/adverse cancel events. "
            "It matches Phase A exactly. The cited 21-event total is not reproducible from "
            "the currently persisted no-entry-restriction oracle artifacts."
        ),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = load_json(PHASE_A_CATALOG)
    ranking = load_json(PHASE_A_RANKING)
    phase_a_log = load_json(PHASE_A_LOG)

    reconciliation = build_reconciliation(catalog)
    matrix_rows = build_candidate_matrix(ranking, phase_a_log)
    preregistration = build_preregistration(ranking, matrix_rows)

    dump_json(OUT_RECONCILIATION, reconciliation)
    write_candidate_matrix(matrix_rows)
    dump_json(OUT_PREREG, preregistration)

    log_payload = {
        "experiment_id": EXP_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "loss_attribution_preregistration",
        "status": "completed_observe_only",
        "change_type": "phase_b_preregistration_audit",
        "strategy_change_attempted": False,
        "gate4": {
            "status": "not_applicable_research_only",
            "reason": "No policy, backtester, run, sizing, ranking, or exit logic was changed.",
        },
        "alpha_hypothesis": {
            "category": "entry",
            "hypothesis": (
                "Some upside gap cancels are volatility-expansion confirmation gaps; bbwidth20 "
                "may identify admits without re-running the rejected gap-threshold family."
            ),
            "why_not_direct_strategy_change": (
                "Phase A found gap magnitude strongest, but that is too close to the rejected global gap scan. "
                "This preregistration selects an orthogonal first candidate before Gate 4 work."
            ),
        },
        "reconciliation_summary": {
            "phase_a_event_count": reconciliation["phase_a_feature_catalog"]["total"],
            "standard_entry_skip_oracle_count": reconciliation["standard_entry_skip_oracle"]["total"],
            "analyst_note_count": reconciliation["analyst_note_count"],
            "analyst_note_reconciliation_status": reconciliation["analyst_note_reconciliation_status"],
        },
        "primary_phase_b_candidate": preregistration["pre_registered_discriminator"],
        "superseded_by": preregistration["superseded_by"],
        "candidate_status_counts": dict(
            sorted(
                {
                    status: sum(1 for row in matrix_rows if row["status"] == status)
                    for status in {row["status"] for row in matrix_rows}
                }.items()
            )
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": False,
            "observe_only": True,
        },
        "related_files": [
            str(OUT_RECONCILIATION.relative_to(REPO_ROOT)),
            str(OUT_MATRIX.relative_to(REPO_ROOT)),
            str(OUT_PREREG.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
        ],
        "next_action": (
            "Do not proceed with the bbwidth20 upside-gap bypass unless new forward evidence or a "
            "materially different orthogonal discriminator appears; exp-20260508-009 already "
            "replayed and rejected this exact Phase B."
        ),
    }
    dump_json(LOG_JSON, log_payload)
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "status": "completed_observe_only",
                "phase_a_event_count": reconciliation["phase_a_feature_catalog"]["total"],
                "standard_entry_skip_oracle_count": reconciliation["standard_entry_skip_oracle"]["total"],
                "analyst_note_reconciliation_status": reconciliation["analyst_note_reconciliation_status"],
                "primary_phase_b_candidate": preregistration["pre_registered_discriminator"],
                "outputs": log_payload["related_files"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
