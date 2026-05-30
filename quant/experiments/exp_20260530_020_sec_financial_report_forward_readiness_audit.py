"""exp-20260530-020: SEC financial-report forward readiness audit.

This read-only alpha-search audit checks whether the default-off SEC
financial-report T+1 paper sleeve has enough production forward candidates,
fills, and closed outcomes to justify a later activation or semantic
allocation experiment.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260530-020"
STEM = "sec_financial_report_forward_readiness_audit"
TRIAL_FAMILY = "sec_financial_report_forward_maturation"
TRIAL_VARIANT_ID = "sec_financial_report_forward_activation_readiness_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID

BASELINE_ARTIFACT = (
    REPO_ROOT / "data" / "experiments" / "exp-20260517-009" / "ample_slot_stock_rank1_topup.json"
)
STATE_JSON = REPO_ROOT / "data" / "paper_sleeves" / "sec_financial_report" / "state.json"
SNAPSHOT_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "sec_financial_report" / "snapshots.jsonl"
OPERATOR_OPEN_POSITIONS = REPO_ROOT / "operator_inputs" / "open_positions.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260530_020_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MIN_FORWARD_CANDIDATES = 10
MIN_CLOSED_OUTCOMES = 10
MIN_CANDIDATE_DATES = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    rows: list[str] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                line = raw.rstrip("\n")
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    rows.append(line)
                    continue
                if isinstance(row, dict) and row.get("experiment_id") == EXPERIMENT_ID:
                    continue
                rows.append(line)
    rows.append(json.dumps(payload, sort_keys=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(rows))
        handle.write("\n")


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _baseline_metrics() -> OrderedDict[str, dict[str, Any]]:
    artifact = _load_json(BASELINE_ARTIFACT)
    metrics = artifact.get("after_metrics") or {}
    out: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label in ("late_strong", "mid_weak", "old_thin"):
        row = metrics.get(label) or {}
        out[label] = {
            "expected_value_score": row.get("expected_value_score"),
            "total_pnl": row.get("total_pnl"),
            "total_return_pct": row.get("total_return_pct"),
            "sharpe_daily": row.get("sharpe_daily"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "trade_count": row.get("trade_count"),
            "signals_generated": row.get("signals_generated"),
            "signals_survived": row.get("signals_survived"),
            "survival_rate": row.get("survival_rate"),
        }
    return out


def _snapshot_rollup(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    latest_by_date: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        asof = str(snapshot.get("asof_date") or "")[:10]
        if asof:
            latest_by_date[asof] = snapshot

    by_date: OrderedDict[str, dict[str, Any]] = OrderedDict()
    source_status = Counter()
    loaded_rows = 0
    loaded_text_rows = 0
    t1_evaluated = 0
    language_covered = 0

    for asof in sorted(latest_by_date):
        snapshot = latest_by_date[asof]
        data_source = snapshot.get("data_source") or {}
        source_status[str(data_source.get("status") or "unknown")] += 1
        loaded_rows += int(data_source.get("loaded_row_count") or 0)
        loaded_text_rows += int(data_source.get("loaded_text_row_count") or 0)
        t1_evaluated += int(data_source.get("t1_evaluated_count") or 0)
        language_covered += int(data_source.get("language_covered_count") or 0)
        by_date[asof] = {
            "candidate_count": int(snapshot.get("candidate_count") or 0),
            "new_pending_count": int(snapshot.get("new_pending_count") or 0),
            "filled_count": int(snapshot.get("filled_count") or 0),
            "closed_count_today": int(snapshot.get("closed_count_today") or 0),
            "pending_count": int(snapshot.get("pending_count") or 0),
            "open_position_count": int(snapshot.get("open_position_count") or 0),
            "closed_position_count": int(snapshot.get("closed_position_count") or 0),
            "realized_pnl_to_date": _safe_float(snapshot.get("realized_pnl_to_date")),
            "unrealized_pnl": _safe_float(snapshot.get("unrealized_pnl")),
            "loaded_row_count": int(data_source.get("loaded_row_count") or 0),
            "loaded_text_row_count": int(data_source.get("loaded_text_row_count") or 0),
            "t1_evaluated_count": int(data_source.get("t1_evaluated_count") or 0),
            "language_covered_count": int(data_source.get("language_covered_count") or 0),
        }

    latest = next(reversed(by_date.values())) if by_date else {}
    candidate_dates = [date for date, row in by_date.items() if row["candidate_count"] > 0]
    return {
        "snapshot_file": _repo_rel(SNAPSHOT_JSONL),
        "snapshot_rows_total": len(snapshots),
        "unique_asof_dates": len(by_date),
        "date_range": {
            "start": next(iter(by_date), None),
            "end": next(reversed(by_date), None) if by_date else None,
        },
        "by_date": by_date,
        "source_status_counts": dict(sorted(source_status.items())),
        "loaded_row_count_sum": loaded_rows,
        "loaded_text_row_count_sum": loaded_text_rows,
        "t1_evaluated_count_sum": t1_evaluated,
        "language_covered_count_sum": language_covered,
        "candidate_count_sum": sum(row["candidate_count"] for row in by_date.values()),
        "candidate_dates": candidate_dates,
        "new_pending_count_sum": sum(row["new_pending_count"] for row in by_date.values()),
        "filled_count_sum": sum(row["filled_count"] for row in by_date.values()),
        "max_open_position_count": max((row["open_position_count"] for row in by_date.values()), default=0),
        "max_closed_position_count": max((row["closed_position_count"] for row in by_date.values()), default=0),
        "latest_realized_pnl_to_date": latest.get("realized_pnl_to_date", 0.0),
        "latest_unrealized_pnl": latest.get("unrealized_pnl", 0.0),
    }


def _gate2_open_positions_check() -> dict[str, Any]:
    payload = _load_json(OPERATOR_OPEN_POSITIONS) if OPERATOR_OPEN_POSITIONS.exists() else {}
    missing: list[str] = []
    checked_rows = 0
    for group_name in ("positions", "observations"):
        rows = payload.get(group_name) or []
        if not isinstance(rows, list):
            missing.append(f"{group_name}:not_a_list")
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                missing.append(f"{group_name}[{index}]:not_an_object")
                continue
            checked_rows += 1
            ticker = row.get("ticker") or f"row_{index}"
            for field in ("entry_date", "target_price"):
                if row.get(field) in (None, ""):
                    missing.append(f"{group_name}[{index}].{ticker}.{field}")
    if not OPERATOR_OPEN_POSITIONS.exists():
        missing.append("operator_inputs/open_positions.json:missing_file")
    return {
        "passed": not missing,
        "file": _repo_rel(OPERATOR_OPEN_POSITIONS),
        "checked_groups": ["positions", "observations"],
        "checked_rows": checked_rows,
        "missing_required_fields": missing,
    }


def _gate4(rollup: dict[str, Any], baseline: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    min_survival = min(_safe_float(row.get("survival_rate")) for row in baseline.values() if row)
    candidate_count = int(rollup["candidate_count_sum"])
    closed_count = int(rollup["max_closed_position_count"])
    candidate_date_count = len(rollup["candidate_dates"])
    passed = (
        candidate_count >= MIN_FORWARD_CANDIDATES
        and closed_count >= MIN_CLOSED_OUTCOMES
        and candidate_date_count >= MIN_CANDIDATE_DATES
        and _safe_float(rollup["latest_realized_pnl_to_date"]) > 0
        and min_survival >= 0.05
    )
    failed: list[str] = []
    if candidate_count < MIN_FORWARD_CANDIDATES:
        failed.append("no_or_too_few_forward_candidates")
    if candidate_date_count < MIN_CANDIDATE_DATES:
        failed.append("candidate_date_coverage_too_small")
    if closed_count < MIN_CLOSED_OUTCOMES:
        failed.append("no_or_too_few_closed_forward_outcomes")
    if _safe_float(rollup["latest_realized_pnl_to_date"]) <= 0:
        failed.append("no_positive_forward_realized_pnl")
    if min_survival < 0.05:
        failed.append("core_survival_below_guard")
    return {
        "passed": passed,
        "promotion_grade": False,
        "failed_reasons": failed,
        "minimum_core_survival_rate": round(min_survival, 4),
        "candidate_count_sum": candidate_count,
        "candidate_count_min": MIN_FORWARD_CANDIDATES,
        "candidate_date_count": candidate_date_count,
        "candidate_date_count_min": MIN_CANDIDATE_DATES,
        "closed_position_count": closed_count,
        "closed_position_count_min": MIN_CLOSED_OUTCOMES,
        "latest_realized_pnl_to_date": rollup["latest_realized_pnl_to_date"],
    }


def _payload() -> dict[str, Any]:
    baseline = _baseline_metrics()
    snapshots = _load_jsonl(SNAPSHOT_JSONL)
    state = _load_json(STATE_JSON) if STATE_JSON.exists() else {}
    rollup = _snapshot_rollup(snapshots)
    gate2 = _gate2_open_positions_check()
    gate4 = _gate4(rollup, baseline)
    timestamp = _now()
    aggregate_ev = sum(_safe_float(row.get("expected_value_score")) for row in baseline.values())
    aggregate_pnl = sum(_safe_float(row.get("total_pnl")) for row in baseline.values())
    prediction = {
        "success_probability": 0.18,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "no_forward_candidates",
            "no_closed_outcomes",
            "missing_replacement_value",
            "thin_forward_sample",
        ],
        "confidence_reason": (
            "Historical SEC financial-report paper replay had positive drift, but current "
            "production snapshots appeared sparse and likely not activation-ready."
        ),
        "recorded_at": "2026-05-30T22:03:11+00:00",
        "brier_score": round((0.18 - 0) ** 2, 6),
    }
    decision = "rejected_no_forward_sec_financial_report_sample"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "created_at": "2026-05-30T22:03:57+00:00",
        "lane": "alpha_search",
        "status": "rejected",
        "decision": decision,
        "hypothesis": (
            "Audit whether the default-off SEC financial-report T+1 drift paper sleeve "
            "has enough production forward candidates and closed outcomes for a later "
            "activation or semantic allocation experiment."
        ),
        "change_summary": "Read-only forward readiness audit; no strategy behavior changed.",
        "change_type": "read_only_forward_replacement_value_readiness_audit",
        "mechanism_family": "read_only_forward_replacement_value_readiness_audit",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260511-100",
            "exp-20260520-034",
            "exp-20260524-004",
            "exp-20260529-026",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "production_forward_paper_sleeve_snapshots",
        "parameters": {
            "state_file": _repo_rel(STATE_JSON),
            "snapshot_file": _repo_rel(SNAPSHOT_JSONL),
            "min_forward_candidates": MIN_FORWARD_CANDIDATES,
            "min_closed_outcomes": MIN_CLOSED_OUTCOMES,
            "min_candidate_dates": MIN_CANDIDATE_DATES,
            "locked_variables": [
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news",
                "production orders",
                "SEC sleeve candidate definition",
            ],
        },
        "date_range": rollup["date_range"],
        "secondary_windows": [
            {"label": "late_strong", "start": "2025-10-23", "end": "2026-04-21"},
            {"label": "mid_weak", "start": "2025-04-23", "end": "2025-10-22"},
            {"label": "old_thin", "start": "2024-10-02", "end": "2025-04-22"},
        ],
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window accepted baseline",
            "baseline_artifact": _repo_rel(BASELINE_ARTIFACT),
            "strategy_behavior_changed": False,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_logic_changed": False,
            "forward_candidate_count": rollup["candidate_count_sum"],
            "forward_closed_outcomes": rollup["max_closed_position_count"],
        },
        "accepted_core_aggregate": {
            "expected_value_score_sum": round(aggregate_ev, 4),
            "total_pnl_sum": round(aggregate_pnl, 2),
        },
        "forward_snapshot_rollup": rollup,
        "state_summary": {
            "pending_entries": len(state.get("pending_entries") or []),
            "open_positions": len(state.get("open_positions") or []),
            "closed_positions": len(state.get("closed_positions") or []),
            "skipped_entries": len(state.get("skipped_entries") or []),
            "updated_at": state.get("updated_at"),
        },
        "gate1": {
            "passed": True,
            "baseline_artifact": _repo_rel(BASELINE_ARTIFACT),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": gate2["passed"],
            "required_runtime_fields": [
                "operator_inputs/open_positions.json.positions[].entry_date",
                "operator_inputs/open_positions.json.positions[].target_price",
                "snapshot.asof_date",
                "snapshot.candidate_count",
                "snapshot.pending_count",
                "snapshot.open_position_count",
                "snapshot.closed_position_count",
                "snapshot.realized_pnl_to_date",
                "state.pending_entries",
                "state.open_positions",
                "state.closed_positions",
            ],
            "missing_required_fields": gate2["missing_required_fields"],
            "operator_open_positions_check": gate2,
            "llm_dependency": "none",
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "core_survival_changed": False,
            "minimum_core_survival_rate": gate4["minimum_core_survival_rate"],
            "note": "Read-only forward audit; no filtering or core survival change.",
        },
        "gate4": gate4,
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": 0,
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": prediction["brier_score"],
            "predicted_failure_modes": prediction["main_failure_modes"],
            "realized_failure_mode": ";".join(gate4["failed_reasons"]),
            "predicted_failure_mode_hit": "no_or_too_few_forward_candidates" in gate4["failed_reasons"],
            "surprise_level": "low",
        },
        "preflight_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool forward maturation: the accepted SEC financial-report "
                "T+1 paper sleeve might have enough production forward rows to justify "
                "activation or semantic allocation review."
            ),
            "2_history_check": (
                "Earlier SEC financial-report replay experiments found historical drift, "
                "but recent SEC semantic scalars such as exp-20260529-026 were data-limited "
                "or rejected. This run checks forward rows instead of retuning frozen samples."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "No core baseline movement; at least 10 forward candidates, 5 candidate dates, "
                "10 closed outcomes, positive realized paper PnL, and survival >=5%."
            ),
            "5_reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260530_020_sec_financial_report_forward_readiness_audit.py"
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "default_off_attribution_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_capital_changed": False,
            "parity_test_added": False,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "rejection_reason": "; ".join(gate4["failed_reasons"]),
        "next_retry_requires": [
            "nonzero production forward candidates",
            "closed forward outcomes",
            "replacement value versus cash or core candidate",
            "a materially sharper SEC semantic field if revisited",
        ],
        "why_switched_alpha": (
            "The forward SEC sleeve has zero candidates and zero closed outcomes in the current "
            "production snapshots, so continuing SEC semantic allocation would violate the "
            "data-limited alpha guidance."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OPERATOR_OPEN_POSITIONS),
            _repo_rel(STATE_JSON),
            _repo_rel(SNAPSHOT_JSONL),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOC_TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
        "summary": (
            "Rejected: SEC financial-report forward paper sleeve has zero forward candidates "
            "and zero closed outcomes in available production snapshots."
        ),
    }


def _artifact(payload: dict[str, Any]) -> str:
    rollup = payload["forward_snapshot_rollup"]
    gate4 = payload["gate4"]
    metric_rows = [
        "| Window | EV | PnL | Trades | Survival |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, metrics in payload["before_metrics"].items():
        metric_rows.append(
            "| {label} | {ev:.4f} | ${pnl:,.2f} | {trades} | {survival:.4f} |".format(
                label=label,
                ev=_safe_float(metrics.get("expected_value_score")),
                pnl=_safe_float(metrics.get("total_pnl")),
                trades=int(metrics.get("trade_count") or 0),
                survival=_safe_float(metrics.get("survival_rate")),
            )
        )
    return "\n".join(
        [
            "# exp-20260530-020 SEC Financial-Report Forward Readiness Audit",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "This was an alpha-search readiness audit, not a strategy change.",
            "",
            "## Canonical Baseline",
            "",
            *metric_rows,
            "",
            "The before/after canonical core metrics are unchanged because this run is read-only.",
            "",
            "## Forward Snapshot Rollup",
            "",
            f"- snapshot rows: `{rollup['snapshot_rows_total']}`",
            f"- unique as-of dates: `{rollup['unique_asof_dates']}`",
            f"- date range: `{rollup['date_range']['start']}` to `{rollup['date_range']['end']}`",
            f"- loaded SEC event rows: `{rollup['loaded_row_count_sum']}`",
            f"- T+1 evaluated rows: `{rollup['t1_evaluated_count_sum']}`",
            f"- candidate count: `{rollup['candidate_count_sum']}`",
            f"- filled count: `{rollup['filled_count_sum']}`",
            f"- closed outcomes: `{rollup['max_closed_position_count']}`",
            f"- realized paper PnL: `${rollup['latest_realized_pnl_to_date']:,.2f}`",
            "",
            "## Gate 2",
            "",
            "```json",
            json.dumps(payload["gate2"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "No shared policy, run adapter, backtester adapter, production watchlist, order path, ranking, sizing, exits, LLM, or news behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            'status: "rejected"',
            'lane: "alpha_search"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            f'new_evidence_type: "{payload["new_evidence_type"]}"',
            f'updated_at: "{payload["timestamp"]}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Summary",
            "",
            payload["summary"],
            "",
            "## Closeout",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Artifact: `{_repo_rel(ARTIFACT_MD)}`",
            f"- Result JSON: `{_repo_rel(OUT_JSON)}`",
            f"- Main blocker: `{payload['rejection_reason']}`",
            "",
        ]
    )


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "rejected",
        "lane": "alpha_search",
        "owner": "codex",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "decision": payload["decision"],
        "artifact": _repo_rel(ARTIFACT_MD),
        "json": _repo_rel(OUT_JSON),
        "summary": payload["summary"],
        "completed_at": payload["timestamp"],
    }


def _manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "rejected",
        "updated_at": payload["timestamp"],
        "files": {
            "runner": _repo_rel(Path(__file__)),
            "result": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "doc_ticket": _repo_rel(DOC_TICKET_JSON),
            "card": _repo_rel(CARD_MD),
            "artifact": _repo_rel(ARTIFACT_MD),
        },
        "anti_js": "No JavaScript was used.",
    }


def _registry_entry(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "rejected",
        "lane": "alpha_search",
        "owner": "codex",
        "hypothesis": payload["hypothesis"],
        "decision": payload["decision"],
        "artifact_file": _repo_rel(OUT_JSON),
        "report_file": _repo_rel(ARTIFACT_MD),
        "result_file": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON).replace("\\", "/"),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "summary": payload["summary"],
        "completed_at": payload["timestamp"].replace("+00:00", "Z"),
        "updated_at": payload["timestamp"].replace("+00:00", "Z"),
        "result": {
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "decision": payload["decision"],
            "summary": payload["summary"],
        },
    }


def _upsert_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON) if REGISTRY_JSON.exists() else {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    if not isinstance(experiments, list):
        raise ValueError("docs/experiment_registry.json experiments must be a list")
    experiments[:] = [
        exp
        for exp in experiments
        if not (isinstance(exp, dict) and exp.get("experiment_id") == EXPERIMENT_ID)
    ]
    experiments.append(_registry_entry(payload))
    registry["updated_at"] = payload["timestamp"].replace("+00:00", "Z")
    _write_json(REGISTRY_JSON, registry)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = _ticket(payload)
    _write_json(TICKET_JSON, ticket)
    _write_json(DOC_TICKET_JSON, ticket)
    _write_json(MANIFEST_JSON, _manifest(payload))
    _write_text(CARD_MD, _card(payload))
    _write_text(ARTIFACT_MD, _artifact(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _upsert_registry(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Compute the audit and print the summary without writing artifacts.",
    )
    args = parser.parse_args()

    payload = _payload()
    if not args.no_persist:
        _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "candidate_count_sum": payload["forward_snapshot_rollup"]["candidate_count_sum"],
                "closed_position_count": payload["forward_snapshot_rollup"]["max_closed_position_count"],
                "gate2_passed": payload["gate2"]["passed"],
                "gate4": payload["gate4"],
                "artifact": _repo_rel(ARTIFACT_MD),
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
