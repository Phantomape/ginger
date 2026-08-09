"""Launch five observed-only alpha-factory experiment ledgers.

This runner creates separate experiment records for the five alpha lanes in the
institutional alpha-factory plan. It does not change orders, core ranking,
portfolio heat, entries, exits, fills, or any live path. The only production
surface changes are read-only paper-sleeve attribution fields implemented in
shared modules and covered by unit tests.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(ROOT / "quant"))

from broad_market_paper_sleeve import (  # noqa: E402
    build_broad_market_replacement_value_report,
    load_broad_market_paper_state,
)
from core_misfit_paper_sleeve import (  # noqa: E402
    build_core_misfit_no_trade_alpha_report,
    load_core_misfit_paper_state,
)
from experiment_history import build_history_report  # noqa: E402
from sec_financial_report_event_sleeve import (  # noqa: E402
    build_fact_tone_gap_attribution,
    load_sec_financial_report_event_sleeve_state,
)
from state_surface_sleeve import (  # noqa: E402
    build_state_surface_concentration_context,
    load_state_surface_sleeve_state,
)


DATE = "20260520"
START_ID = 27
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


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _latest_jsonl(path: Path) -> dict[str, Any]:
    rows = _jsonl_rows(path)
    return rows[-1] if rows else {}


def _latest_backtest_result() -> tuple[Path | None, dict[str, Any]]:
    paths = sorted((ROOT / "data" / "backtests").glob("backtest_results_*.json"))
    paths = [path for path in paths if "diagnostics" not in path.name]
    for path in reversed(paths):
        try:
            return path, json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
    return None, {}


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


def _snapshot_summary(path: Path) -> dict[str, Any]:
    row = _latest_jsonl(path)
    return {
        "path": _repo_rel(path),
        "asof_date": row.get("asof_date"),
        "candidate_count": row.get("candidate_count"),
        "pending_count": row.get("pending_count"),
        "open_position_count": row.get("open_position_count"),
        "closed_position_count": row.get("closed_position_count"),
        "closed_outcome_count": row.get("closed_outcome_count"),
        "primary_closed_outcome_count": row.get("primary_closed_outcome_count"),
        "realized_pnl_to_date": row.get("realized_pnl_to_date"),
        "realized_no_trade_value_to_date": row.get("realized_no_trade_value_to_date"),
        "realized_inverse_pnl_to_date": row.get("realized_inverse_pnl_to_date"),
        "forward_paper_gate": row.get("forward_paper_gate"),
        "data_source": row.get("data_source"),
    }


def _broad_market_evidence() -> dict[str, Any]:
    state = load_broad_market_paper_state()
    report = build_broad_market_replacement_value_report(
        candidates=[],
        pending_entries=state.get("pending_entries") or [],
        open_positions=state.get("open_positions") or [],
        closed_positions=state.get("closed_positions") or [],
        skipped_entries=state.get("skipped_entries") or [],
    )
    return {
        "current_snapshot": _snapshot_summary(
            ROOT / "data" / "paper_sleeves" / "broad_market" / "snapshots.jsonl"
        ),
        "replacement_value_report": report,
        "field_status": "implemented_in_shared_paper_sleeve_next_snapshot",
    }


def _state_surface_evidence() -> dict[str, Any]:
    state = load_state_surface_sleeve_state()
    sample = build_state_surface_concentration_context(
        {"ticker": "SAMPLE", "sector": "Technology", "surface": "rotation"},
        [
            {"ticker": "SAMPLE", "sector": "Technology", "surface": "rotation"},
            {"ticker": "PEER", "sector": "Technology", "surface": "rotation"},
        ],
        closed_positions=state.get("closed_positions") or [],
    )
    return {
        "current_snapshot": _snapshot_summary(
            ROOT / "data" / "paper_sleeves" / "state_surface" / "snapshots.jsonl"
        ),
        "sample_concentration_context": sample,
        "field_status": "implemented_in_shared_paper_sleeve_next_snapshot",
    }


def _sec_evidence() -> dict[str, Any]:
    state = load_sec_financial_report_event_sleeve_state()
    sample = build_fact_tone_gap_attribution(
        {
            "ticker": "SAMPLE",
            "usable_trade_date": "2026-05-20",
            "accession_number": "sample",
            "event_family": "earnings_8k",
            "form_base": "8-K",
            "text_event_type": "earnings_release_text",
            "language_bucket": "positive_language",
            "positive_phrase_hits": ["revenue increased"],
            "guidance_raise_hits": ["raised outlook"],
        }
    )
    return {
        "current_snapshot": _snapshot_summary(
            ROOT / "data" / "paper_sleeves" / "sec_financial_report" / "snapshots.jsonl"
        ),
        "state_counts": {
            "pending": len(state.get("pending_entries") or []),
            "open": len(state.get("open_positions") or []),
            "closed": len(state.get("closed_positions") or []),
        },
        "sample_fact_tone_gap_attribution": sample,
        "field_status": "implemented_in_shared_paper_sleeve_next_snapshot",
    }


def _core_misfit_evidence() -> dict[str, Any]:
    state = load_core_misfit_paper_state()
    primary_horizon = 10
    primary = [
        row
        for row in state.get("closed_outcomes") or []
        if int(row.get("horizon_days") or 0) == primary_horizon
    ]
    report = build_core_misfit_no_trade_alpha_report(
        primary_closed_outcomes=primary,
        open_positions=state.get("open_positions") or [],
    )
    return {
        "current_snapshot": _snapshot_summary(
            ROOT / "data" / "paper_sleeves" / "core_misfit" / "snapshots.jsonl"
        ),
        "no_trade_alpha_report": report,
    }


def _execution_evidence() -> dict[str, Any]:
    path, payload = _latest_backtest_result()
    attribution = payload.get("entry_execution_attribution") or {}
    reason_counts = attribution.get("reason_counts") or {}
    candidate_events = int(attribution.get("candidate_events") or 0)
    entered = int(attribution.get("entered_count") or reason_counts.get("entered") or 0)
    skipped = int(attribution.get("skipped_count") or 0)
    return {
        "source_backtest": _repo_rel(path) if path else None,
        "entry_execution_attribution": {
            "candidate_events": candidate_events,
            "entered_count": entered,
            "skipped_count": skipped,
            "skip_rate": round(skipped / candidate_events, 4) if candidate_events else None,
            "reason_counts": reason_counts,
            "gap_cancel_count": int(reason_counts.get("gap_cancel") or 0),
            "adverse_gap_down_cancel_count": int(
                reason_counts.get("adverse_gap_down_cancel") or 0
            ),
            "sample_skips": (attribution.get("sample_skips") or [])[:5],
        },
        "manual_delay_source_available": False,
        "next_required_field": "live_order_decision_timestamp_vs_planned_next_open",
    }


LANES = [
    {
        "slug": "broad_market_forward_maturation",
        "mechanism_family": "broad_market_forward_maturation",
        "trial_family": "broad_market_forward_maturation",
        "trial_variant_id": "replacement_value_report_v1",
        "changed_variable": "broad_market_replacement_value_report",
        "new_evidence_type": "new_replacement_value_report",
        "keywords": ["broad_market"],
        "component": "quant/broad_market_paper_sleeve.py",
        "hypothesis": (
            "Broad-market leadership should mature as a daily paper ledger with "
            "closed/open/pending replacement value before any core expansion."
        ),
        "evidence_fn": _broad_market_evidence,
        "next_evidence_needed": (
            "Populate the candidate universe feed, then collect closed 20d "
            "replacement-value outcomes versus paper cash or displaced core slots."
        ),
    },
    {
        "slug": "state_surface_concentration_context",
        "mechanism_family": "state_surface_concentration",
        "trial_family": "state_surface_concentration_context",
        "trial_variant_id": "context_field_v1",
        "changed_variable": "state_surface_concentration_context",
        "new_evidence_type": "new_production_visible_field",
        "keywords": ["state_surface"],
        "component": "quant/state_surface_sleeve.py",
        "hypothesis": (
            "State-surface scalar mining should pause until candidates expose a "
            "PIT-safe concentration field for same ticker, sector, theme, recent "
            "winner contribution, and queue independence."
        ),
        "evidence_fn": _state_surface_evidence,
        "next_evidence_needed": (
            "Wait for selected paper candidates carrying the field, then only "
            "test scalars if the strict >10% aggregate EV gate is pre-registered."
        ),
    },
    {
        "slug": "sec_fact_tone_gap_field",
        "mechanism_family": "sec_earnings_semantic_field",
        "trial_family": "sec_fact_tone_gap_bucket",
        "trial_variant_id": "fact_tone_gap_bucket_v1",
        "changed_variable": "fact_tone_gap_bucket",
        "new_evidence_type": "new_production_visible_field",
        "keywords": ["sec_financial", "earnings"],
        "component": "quant/sec_financial_report_event_sleeve.py",
        "hypothesis": (
            "SEC earnings attribution should separate factual improvement, tone "
            "packaging, and fact-tone divergence before testing another notional "
            "scalar."
        ),
        "evidence_fn": _sec_evidence,
        "next_evidence_needed": (
            "Collect forward returns, replacement value, and veto/allow "
            "attribution by fact_tone_gap_bucket."
        ),
    },
    {
        "slug": "core_misfit_no_trade_alpha",
        "mechanism_family": "core_misfit_no_trade",
        "trial_family": "core_misfit_no_trade_forward_maturation",
        "trial_variant_id": "no_trade_alpha_report_v1",
        "changed_variable": "core_misfit_no_trade_alpha_report",
        "new_evidence_type": "new_no_trade_alpha_report",
        "keywords": ["core_misfit"],
        "component": "quant/core_misfit_paper_sleeve.py",
        "hypothesis": (
            "Core-misfit alpha should first prove avoided long-loss value on "
            "closed 10d paper outcomes rather than jumping to live shorts."
        ),
        "evidence_fn": _core_misfit_evidence,
        "next_evidence_needed": (
            "Reach at least 20 closed 10d outcomes with positive no-trade "
            "avoided value before any exclusion or live-path haircut test."
        ),
    },
    {
        "slug": "execution_leakage_attribution",
        "mechanism_family": "execution_slippage_leakage",
        "trial_family": "execution_leakage_report",
        "trial_variant_id": "entry_execution_attribution_v1",
        "changed_variable": "execution_leakage_report",
        "new_evidence_type": "new_execution_attribution_report",
        "keywords": ["execution", "slippage", "gap_cancel"],
        "component": "quant/backtester.py",
        "hypothesis": (
            "Execution alpha should quantify planned next-open fills, gap "
            "erosion, cancel reasons, and missing live delay telemetry before "
            "testing a shared execution policy variable."
        ),
        "evidence_fn": _execution_evidence,
        "next_evidence_needed": (
            "Add live planned-vs-actual timestamp and fill telemetry; only then "
            "test one shared execution policy variable such as net R:R invalidation."
        ),
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
    return {
        "experiment_id": experiment_id,
        "timestamp": now,
        "status": "observed_only",
        "decision": "observed_only_launch_recorded",
        "lane": "alpha_search",
        "hypothesis": lane["hypothesis"],
        "change_summary": f"Create observed-only {lane['slug']} alpha experiment ledger.",
        "change_type": "observed_only_alpha_experiment",
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
            "observed_only": True,
            "live_orders_changed": False,
            "core_strategy_metrics_expected_to_change": False,
            "most_recent_failure": history["most_recent_failure"],
        },
        "date_range": {"as_of": "2026-05-20"},
        "before_metrics": {"canonical_core_metrics_changed": False},
        "after_metrics": {"canonical_core_metrics_changed": False},
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
        },
        "expected_value_score_delta": 0.0,
        "current_evidence": evidence,
        "acceptance_status": {
            "observed_only_artifact_created": True,
            "strategy_gate4_required": False,
            "reason": "No trading decision, ranking, sizing, entry, exit, or fill policy changed.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "production_visible_attribution_changed": lane["slug"]
            in {
                "state_surface_concentration_context",
                "sec_fact_tone_gap_field",
                "broad_market_forward_maturation",
                "core_misfit_no_trade_alpha",
            },
        },
        "next_evidence_needed": lane["next_evidence_needed"],
        "related_files": [
            lane["component"],
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
            "## Current Evidence",
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
    meta_report = build_history_report(ROOT)
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
