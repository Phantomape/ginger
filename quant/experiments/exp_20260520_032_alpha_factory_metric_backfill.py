"""Backfill metric-backed evidence records for the five alpha-factory lanes.

The 027-031 records launched observed-only ledgers. This runner attaches each
lane to the strongest existing replay, backtest, or frozen forward-outcome
artifact available in the repository, and explicitly marks lanes that are not
yet eligible for a live strategy backtest.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(ROOT / "quant"))

from meta_research_engine import build_meta_report  # noqa: E402
from sec_financial_report_event_sleeve import (  # noqa: E402
    build_fact_tone_gap_attribution,
)


DATE = "20260520"
START_ID = 32
EXPERIMENT_LOG_JSONL = ROOT / "docs" / "experiment_log.jsonl"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, Path):
        return _repo_rel(value)
    return value


def _repo_rel(path: Path | str | None) -> str | None:
    if path is None:
        return None
    try:
        return str(Path(path).resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_json(rel_path: str) -> dict[str, Any]:
    path = ROOT / rel_path
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _metric(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _round(value: Any, places: int = 4) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), places)
    return value


def _trial_context(meta_report: dict[str, Any], keywords: list[str]) -> dict[str, Any]:
    groups = []
    for group in (meta_report.get("trial_accounting") or {}).get("groups") or []:
        blob = " ".join(
            [
                str(group.get("trial_family") or ""),
                str(group.get("changed_variable") or ""),
                " ".join(group.get("mechanism_families") or []),
            ]
        ).lower()
        if any(keyword.lower() in blob for keyword in keywords):
            groups.append(group)
    experiments = []
    for group in groups:
        for experiment_id in group.get("recent_experiments") or []:
            if experiment_id not in experiments:
                experiments.append(experiment_id)
    failure = next(
        (group.get("most_recent_failure") for group in groups if group.get("most_recent_failure")),
        None,
    )
    risk_order = {"minimal": 0, "low": 1, "moderate": 2, "high": 3}
    risk = "minimal"
    for group in groups:
        bucket = str(group.get("multiple_testing_risk_bucket") or "minimal")
        if risk_order.get(bucket, 0) > risk_order.get(risk, 0):
            risk = bucket
    return {
        "prior_trial_count": sum(int(group.get("effective_trial_count") or 0) for group in groups),
        "nearby_prior_experiments": experiments[:10],
        "multiple_testing_risk_bucket": risk,
        "most_recent_failure": failure,
    }


def _candidate_rows(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        maybe_rows = payload.get("candidate_rows")
        if isinstance(maybe_rows, list):
            rows.extend(row for row in maybe_rows if isinstance(row, dict))
        for value in payload.values():
            rows.extend(_candidate_rows(value))
    elif isinstance(payload, list):
        for value in payload:
            rows.extend(_candidate_rows(value))
    return rows


def _numeric_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    values = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _summarize_numeric(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = _numeric_values(rows, key)
    if not values:
        return {"count": 0}
    wins = sum(1 for value in values if value > 0)
    return {
        "count": len(values),
        "avg": _round(mean(values), 6),
        "sum": _round(sum(values), 2),
        "win_rate": _round(wins / len(values), 4),
        "min": _round(min(values), 4),
        "max": _round(max(values), 4),
    }


def _broad_market_evidence() -> dict[str, Any]:
    rel = "data/experiments/exp-20260520-022/cien_technology_haircut_exception_summary.json"
    summary = _read_json(rel)
    return {
        "evidence_type": "canonical_three_window_backtest",
        "source_experiment": "exp-20260520-022",
        "source_artifact": rel,
        "baseline_experiment": _metric(summary, "before_metrics", "baseline_experiment"),
        "before_aggregate": _metric(summary, "before_metrics", "aggregate"),
        "after_aggregate": _metric(summary, "after_metrics", "aggregate"),
        "delta_aggregate": _metric(summary, "delta_metrics", "aggregate"),
        "selected_trade_count": _metric(summary, "after_metrics", "aggregate", "cien_selected_trade_count"),
        "gate_assessment": summary.get("gate_assessment"),
        "decision": summary.get("decision"),
        "rejection_reason": summary.get("rejection_reason"),
    }


def _state_surface_evidence() -> dict[str, Any]:
    rel = "data/experiments/exp-20260520-006/state_surface_trend_stability_notional.json"
    replay = _read_json(rel)
    tail_rel = "data/experiments/exp-20260518-006/state_surface_forward_tail_gate.json"
    tail = _read_json(tail_rel)
    return {
        "evidence_type": "state_surface_paper_replay_and_tail_gate",
        "source_experiment": "exp-20260520-006",
        "source_artifact": rel,
        "strict_state_surface_gate": {
            "minimum_aggregate_ev_delta_pct": _metric(
                replay,
                "gate4",
                "minimum_aggregate_ev_delta_pct",
            ),
            "actual_aggregate_ev_delta_pct": _metric(
                replay,
                "delta_metrics",
                "aggregate_ev_delta_pct",
            ),
            "aggregate_ev_delta": _metric(replay, "delta_metrics", "aggregate_ev_delta"),
            "aggregate_pnl_delta": _metric(replay, "delta_metrics", "aggregate_pnl_delta"),
            "windows_ev_improved": _metric(replay, "delta_metrics", "windows_ev_improved"),
            "windows_ev_regressed": _metric(replay, "delta_metrics", "windows_ev_regressed"),
            "passed": _metric(replay, "gate4", "passed"),
        },
        "tail_gate_reference": {
            "source_experiment": "exp-20260518-006",
            "source_artifact": tail_rel,
            "closed_trades": _metric(
                tail,
                "after_metrics",
                "tail_aware_forward_gate",
                "metrics",
                "closed_trades",
            ),
            "realized_pnl": _metric(
                tail,
                "after_metrics",
                "tail_aware_forward_gate",
                "metrics",
                "realized_pnl",
            ),
            "win_rate": _metric(
                tail,
                "after_metrics",
                "tail_aware_forward_gate",
                "metrics",
                "win_rate",
            ),
            "passed": _metric(tail, "after_metrics", "tail_aware_forward_gate", "passed"),
            "block_reasons": _metric(
                tail,
                "after_metrics",
                "tail_aware_forward_gate",
                "reasons",
            ),
        },
        "decision": replay.get("decision"),
        "rejection_reason": replay.get("rejection_reason"),
    }


def _sec_evidence() -> dict[str, Any]:
    rel = (
        "data/experiments/exp-20260511-100/"
        "exp_20260511_100_sec_financial_report_positive_t1_forward_outcome_refresh.json"
    )
    forward = _read_json(rel)
    scalar_rel = "data/experiments/exp-20260520-008/exp_20260520_008_sec_positive_language_low_reaction_notional.json"
    scalar = _read_json(scalar_rel)
    rows = _candidate_rows(forward)
    unique_rows = {
        (
            row.get("window"),
            row.get("ticker"),
            row.get("accession_number"),
            row.get("usable_trade_date"),
        ): row
        for row in rows
    }
    deduped_rows = list(unique_rows.values())
    bucket_counts = Counter(
        build_fact_tone_gap_attribution(row).get("fact_tone_gap_bucket")
        for row in deduped_rows
    )
    return {
        "evidence_type": "frozen_forward_outcome_plus_prior_notional_replay",
        "forward_source_experiment": "exp-20260511-100",
        "forward_source_artifact": rel,
        "candidate_count": _metric(forward, "aggregate", "candidate_summary", "candidate_count"),
        "deduped_candidate_rows": len(deduped_rows),
        "unique_tickers": _metric(forward, "aggregate", "candidate_summary", "unique_tickers"),
        "event_family_counts": _metric(
            forward,
            "aggregate",
            "candidate_summary",
            "event_family_counts",
        ),
        "refreshed_forward_returns": _metric(
            forward,
            "aggregate",
            "candidate_summary",
            "refreshed_forward_returns",
        ),
        "refreshed_pnl_proxy": _metric(
            forward,
            "aggregate",
            "candidate_summary",
            "refreshed_pnl_proxy",
        ),
        "fact_tone_gap_bucket_counts_on_historical_rows": dict(bucket_counts),
        "fact_tone_gap_historical_limitation": (
            "The frozen SEC forward rows do not carry language_bucket or phrase-hit "
            "provenance, so fact_tone_gap buckets are not yet backtestable by bucket."
        ),
        "prior_scalar_source_experiment": "exp-20260520-008",
        "prior_scalar_source_artifact": scalar_rel,
        "prior_scalar_delta": scalar.get("delta_metrics"),
        "prior_scalar_decision": scalar.get("decision"),
        "prior_scalar_rejection_reason": scalar.get("rejection_reason"),
        "deduped_10d_pnl_proxy": _summarize_numeric(
            deduped_rows,
            "refresh_fwd_10d_pnl_proxy",
        ),
        "deduped_20d_pnl_proxy": _summarize_numeric(
            deduped_rows,
            "refresh_fwd_20d_pnl_proxy",
        ),
    }


def _core_misfit_evidence() -> dict[str, Any]:
    rel = "data/experiments/exp-20260518-022/core_misfit_trend_only_paper_scope.json"
    scope = _read_json(rel)
    shadow_rel = "data/experiments/exp-20260518-019/core_misfit_conditioned_short_shadow.json"
    shadow = _read_json(shadow_rel)
    return {
        "evidence_type": "paper_replay_no_trade_and_conditioned_short_shadow",
        "source_experiment": "exp-20260518-022",
        "source_artifact": rel,
        "core_metrics_changed": _metric(scope, "delta_metrics", "core_metrics_changed"),
        "paper_before": scope.get("paper_before_metrics"),
        "paper_after": scope.get("paper_after_metrics"),
        "paper_delta": scope.get("paper_delta_metrics"),
        "gate4": scope.get("gate4"),
        "decision": scope.get("decision"),
        "interpretation": scope.get("interpretation"),
        "conditioned_short_shadow_reference": {
            "source_experiment": "exp-20260518-019",
            "source_artifact": shadow_rel,
            "selection": shadow.get("selection"),
            "condition_gate_summaries": shadow.get("condition_gate_summaries"),
            "decision": shadow.get("decision"),
            "rejection_reason": shadow.get("rejection_reason"),
        },
        "live_gate_blocker": "Need at least 20 closed 10d CORE_MISFIT_PAPER outcomes before live-path haircut or exclusion tests.",
    }


def _execution_evidence() -> dict[str, Any]:
    rel = "data/backtests/backtest_results_20260520.json"
    latest = _read_json(rel)
    attribution = latest.get("entry_execution_attribution") or {}
    reason_counts = attribution.get("reason_counts") or {}
    candidate_events = int(attribution.get("candidate_events") or 0)
    entered = int(attribution.get("entered_count") or 0)
    skipped = int(attribution.get("skipped_count") or 0)
    return {
        "evidence_type": "latest_backtest_entry_execution_attribution",
        "source_backtest": rel,
        "period": latest.get("period"),
        "core_metrics": {
            "expected_value_score": latest.get("expected_value_score"),
            "total_pnl": latest.get("total_pnl"),
            "signals_generated": latest.get("signals_generated"),
            "signals_survived": latest.get("signals_survived"),
            "survival_rate": latest.get("survival_rate"),
            "trade_count": latest.get("total_trades"),
        },
        "entry_execution_attribution": {
            "candidate_events": candidate_events,
            "entered_count": entered,
            "skipped_count": skipped,
            "skip_rate": _round(skipped / candidate_events, 4) if candidate_events else None,
            "reason_counts": reason_counts,
            "gap_related_skip_count": int(reason_counts.get("gap_cancel") or 0)
            + int(reason_counts.get("adverse_gap_down_cancel") or 0),
            "sample_skips": (attribution.get("sample_skips") or [])[:8],
        },
        "limitation": (
            "This quantifies skipped entry decisions in replay, but live planned-vs-actual "
            "timestamps and realized fill slippage are still missing."
        ),
    }


LANES = [
    {
        "slug": "broad_market_backtest_evidence",
        "status": "rejected",
        "decision": "rejected_existing_backtest_single_trade_concentration",
        "mechanism_family": "broad_market_forward_maturation",
        "trial_family": "broad_market_leadership_forward_maturation",
        "trial_variant_id": "cien_technology_haircut_exception_reference_v1",
        "changed_variable": "technology_haircut_exception_for_cien",
        "new_evidence_type": "canonical_three_window_backtest",
        "keywords": ["broad_market", "cien"],
        "component": "quant/run.py",
        "hypothesis": (
            "A broad-market leadership candidate can replace overly blunt sector haircuts "
            "only if the effect survives multi-window replay without single-trade dependence."
        ),
        "evidence_fn": _broad_market_evidence,
        "next_evidence_needed": "Collect broader closed replacement-value outcomes beyond one CIEN trade before any core exception.",
    },
    {
        "slug": "state_surface_metric_evidence",
        "status": "rejected",
        "decision": "blocked_strict_state_surface_gate_not_met",
        "mechanism_family": "state_surface_concentration",
        "trial_family": "state_surface_concentration_context",
        "trial_variant_id": "prior_scalar_evidence_backfill_v1",
        "changed_variable": "state_surface_trend_stability_support_notional",
        "new_evidence_type": "paper_replay_strict_gate_evidence",
        "keywords": ["state_surface"],
        "component": "quant/state_surface_sleeve.py",
        "hypothesis": (
            "State-surface concentration work should not add another scalar unless the "
            "aggregate EV improvement exceeds the strict >10% gate."
        ),
        "evidence_fn": _state_surface_evidence,
        "next_evidence_needed": "Use the new concentration context field to explain queue concentration before another scalar/profile test.",
    },
    {
        "slug": "sec_fact_tone_gap_metric_evidence",
        "status": "blocked",
        "decision": "blocked_historical_bucket_backtest_missing_phrase_provenance",
        "mechanism_family": "sec_earnings_semantic_field",
        "trial_family": "sec_fact_tone_gap_bucket",
        "trial_variant_id": "historical_forward_outcome_backfill_v1",
        "changed_variable": "fact_tone_gap_bucket",
        "new_evidence_type": "frozen_forward_outcome_with_bucket_blocker",
        "keywords": ["sec_financial", "earnings"],
        "component": "quant/sec_financial_report_event_sleeve.py",
        "hypothesis": (
            "The SEC financial-report queue has positive frozen forward drift, but "
            "fact-tone gap itself cannot be promoted until historical rows carry evidence spans."
        ),
        "evidence_fn": _sec_evidence,
        "next_evidence_needed": "Persist language_bucket, phrase-hit counts, and evidence spans on SEC candidates, then rerun bucketed forward attribution.",
    },
    {
        "slug": "core_misfit_metric_evidence",
        "status": "accepted_default_off",
        "decision": "accepted_default_off_observation_not_live",
        "mechanism_family": "core_misfit_no_trade",
        "trial_family": "core_misfit_no_trade_forward_maturation",
        "trial_variant_id": "paper_replay_reference_v1",
        "changed_variable": "core_misfit_trend_only_paper_scope",
        "new_evidence_type": "paper_replay_no_trade_metrics",
        "keywords": ["core_misfit"],
        "component": "quant/core_misfit_paper_sleeve.py",
        "hypothesis": (
            "Core-misfit should mature as no-trade avoided-value evidence before any "
            "live short, haircut, or exclusion path."
        ),
        "evidence_fn": _core_misfit_evidence,
        "next_evidence_needed": "Reach 20 closed 10d CORE_MISFIT_PAPER outcomes, then test exactly one live-path haircut or exclusion variable.",
    },
    {
        "slug": "execution_leakage_metric_evidence",
        "status": "attribution_only",
        "decision": "attribution_only_backtest_evidence_collected",
        "mechanism_family": "execution_slippage_leakage",
        "trial_family": "execution_leakage_report",
        "trial_variant_id": "latest_entry_execution_attribution_v1",
        "changed_variable": "entry_execution_attribution",
        "new_evidence_type": "latest_backtest_execution_attribution",
        "keywords": ["execution", "slippage", "gap_cancel"],
        "component": "quant/backtester.py",
        "hypothesis": (
            "Execution alpha should first measure planned entry skips, gap cancels, "
            "slot slicing, and no-share decisions before testing a shared execution rule."
        ),
        "evidence_fn": _execution_evidence,
        "next_evidence_needed": "Add live planned-vs-actual timestamp and fill telemetry before testing one shared execution policy variable.",
    },
]


def _record_for_lane(
    lane: dict[str, Any],
    *,
    sequence: int,
    meta_report: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    experiment_id = f"exp-{DATE}-{sequence:03d}"
    history = _trial_context(meta_report, lane["keywords"])
    evidence = lane["evidence_fn"]()
    strategy_backtest = evidence.get("evidence_type") in {
        "canonical_three_window_backtest",
        "state_surface_paper_replay_and_tail_gate",
        "latest_backtest_entry_execution_attribution",
    }
    return {
        "experiment_id": experiment_id,
        "timestamp": now,
        "status": lane["status"],
        "decision": lane["decision"],
        "lane": "alpha_search",
        "hypothesis": lane["hypothesis"],
        "change_summary": f"Backfill metric-backed evidence for {lane['slug']}.",
        "change_type": "metric_backfill_no_strategy_change",
        "mechanism_family": lane["mechanism_family"],
        "trial_family": lane["trial_family"],
        "trial_variant_id": lane["trial_variant_id"],
        "changed_variable": lane["changed_variable"],
        "prior_trial_count": history["prior_trial_count"],
        "nearby_prior_experiments": history["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": history["multiple_testing_risk_bucket"],
        "new_evidence_type": lane["new_evidence_type"],
        "component": lane["component"],
        "parameters": {
            "metric_backfill": True,
            "live_orders_changed": False,
            "core_strategy_logic_changed": False,
            "most_recent_failure": history["most_recent_failure"],
        },
        "date_range": {"as_of": "2026-05-20"},
        "before_metrics": {"strategy_logic_changed": False},
        "after_metrics": {"strategy_logic_changed": False, "metric_evidence_collected": True},
        "delta_metrics": {"expected_value_score": 0.0, "total_pnl": 0.0, "trade_count": 0},
        "expected_value_score_delta": 0.0,
        "current_evidence": evidence,
        "acceptance_status": {
            "strategy_backtest_or_forward_outcome_evidence_attached": True,
            "strategy_backtest_evidence": strategy_backtest,
            "forward_outcome_only": evidence.get("evidence_type", "").startswith("frozen_forward"),
            "strategy_logic_promoted": False,
            "reason": "This record attaches existing metrics; it does not alter orders, ranking, sizing, entries, exits, or fill policy.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
        },
        "next_evidence_needed": lane["next_evidence_needed"],
        "related_files": [
            f"data/experiments/{experiment_id}/{lane['slug']}.json",
            f"experiments/logs/{experiment_id}.json",
            f"experiments/artifacts/{experiment_id}_{lane['slug']}.md",
            "docs/experiment_log.jsonl",
        ],
    }


def _artifact_markdown(record: dict[str, Any]) -> str:
    evidence = json.dumps(_safe(record["current_evidence"]), indent=2, sort_keys=True)
    return "\n".join(
        [
            f"# {record['experiment_id']} {record['trial_variant_id']}",
            "",
            f"Decision: `{record['decision']}`.",
            "",
            "## Hypothesis",
            "",
            record["hypothesis"],
            "",
            "## Trial Accounting",
            "",
            f"- mechanism_family: `{record['mechanism_family']}`",
            f"- trial_family: `{record['trial_family']}`",
            f"- changed_variable: `{record['changed_variable']}`",
            f"- prior_trial_count: `{record['prior_trial_count']}`",
            f"- multiple_testing_risk_bucket: `{record['multiple_testing_risk_bucket']}`",
            "",
            "## Metric Evidence",
            "",
            "```json",
            evidence,
            "```",
            "",
            "## Next Evidence Needed",
            "",
            record["next_evidence_needed"],
            "",
        ]
    )


def _append_experiment_log(records: list[dict[str, Any]]) -> None:
    existing_lines = []
    skip_ids = {record["experiment_id"] for record in records}
    if EXPERIMENT_LOG_JSONL.exists():
        for line in EXPERIMENT_LOG_JSONL.read_text(
            encoding="utf-8-sig",
            errors="replace",
        ).splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                existing_lines.append(line)
                continue
            if row.get("experiment_id") not in skip_ids:
                existing_lines.append(line)
    for record in records:
        existing_lines.append(json.dumps(_safe(record), sort_keys=True))
    EXPERIMENT_LOG_JSONL.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")


def run() -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    meta_report = build_meta_report(ROOT)
    return [
        _record_for_lane(
            lane,
            sequence=START_ID + offset,
            meta_report=meta_report,
            now=now,
        )
        for offset, lane in enumerate(LANES)
    ]


def persist(records: list[dict[str, Any]]) -> None:
    for record, lane in zip(records, LANES):
        experiment_id = record["experiment_id"]
        slug = lane["slug"]
        data_dir = ROOT / "data" / "experiments" / experiment_id
        _write_json(data_dir / f"{slug}.json", record)
        _write_json(ROOT / "experiments" / "logs" / f"{experiment_id}.json", record)
        _write_json(
            ROOT / "experiments" / "tickets" / f"{experiment_id}.json",
            {
                "experiment_id": experiment_id,
                "status": record["status"],
                "summary": record["change_summary"],
                "artifact": f"experiments/artifacts/{experiment_id}_{slug}.md",
                "json": f"data/experiments/{experiment_id}/{slug}.json",
                "trial_family": record["trial_family"],
                "changed_variable": record["changed_variable"],
            },
        )
        _write_text(
            ROOT / "experiments" / "artifacts" / f"{experiment_id}_{slug}.md",
            _artifact_markdown(record),
        )
    _append_experiment_log(records)


def main() -> int:
    records = run()
    persist(records)
    print(
        json.dumps(
            {
                "experiments": [
                    {
                        "experiment_id": record["experiment_id"],
                        "trial_family": record["trial_family"],
                        "changed_variable": record["changed_variable"],
                        "decision": record["decision"],
                        "evidence_type": record["current_evidence"].get("evidence_type"),
                    }
                    for record in records
                ]
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
