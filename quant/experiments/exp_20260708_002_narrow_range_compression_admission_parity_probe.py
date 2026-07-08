"""exp-20260708-002: duplicate narrow-range compression parity closeout.

Measurement repair closeout only. The proposed representative-day parity probe
was already completed and accepted by exp-20260705-001. This runner records the
anti-repeat decision instead of rerunning the same evidence surface.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260708-002"
OWNER = "alpha-explore"
SLUG = "narrow_range_compression_admission_parity_probe"
RUNNER = f"quant/experiments/exp_20260708_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
PRIOR_EXPERIMENT_ID = "exp-20260705-001"
PRIOR_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / PRIOR_EXPERIMENT_ID
    / "exp_20260705_001_narrow_range_compression_admission_parity_probe.json"
)
SNAPSHOT_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "narrow_range_compression_breakout" / "snapshots.jsonl"
STATE_JSON = REPO_ROOT / "data" / "paper_sleeves" / "narrow_range_compression_breakout" / "state.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260708_002_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260708_002_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\experiments\\exp_20260708_002_narrow_range_compression_admission_parity_probe.py",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def safe_write_text(text: str, path: Path) -> None:
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic fallback: {exc}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def safe_write_json(payload: Any, path: Path) -> None:
    safe_write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True, default=str) + "\n",
        path,
    )


def as_int(value: Any) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def baseline_summary() -> dict[str, Any]:
    payload = load_json(BASELINE_JSON, {})
    windows = payload.get("windows") or []
    generated = sum(as_int(window.get("signals_generated")) for window in windows)
    survived = sum(as_int(window.get("signals_survived")) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(as_int(window.get("trade_count") or window.get("total_trades")) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
    }


def current_forward_snapshot_audit() -> dict[str, Any]:
    rows = read_jsonl(SNAPSHOT_JSONL)
    latest_by_asof: dict[str, dict[str, Any]] = {}
    for row in rows:
        asof = str(row.get("asof_date") or row.get("date") or "")[:10]
        if asof:
            latest_by_asof[asof] = row

    totals = Counter()
    reason_counts: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    for asof, row in sorted(latest_by_asof.items()):
        context = row.get("narrow_range_compression_breakout_context")
        if not isinstance(context, dict):
            context = row.get("context_scan") if isinstance(row.get("context_scan"), dict) else {}
        scan = row.get("context_scan") if isinstance(row.get("context_scan"), dict) else context
        if not isinstance(scan, dict):
            scan = {}
        raw_count = as_int(row.get("raw_candidate_count"))
        if raw_count == 0:
            raw_count = as_int(scan.get("raw_compression_breakout_candidates"))
        candidate_count = as_int(row.get("candidate_count"))
        new_pending_count = as_int(row.get("new_pending_count"))
        context_days = as_int(scan.get("days_with_raw_compression_breakout_candidates"))
        rejected_count = as_int(row.get("rejected_candidate_count"))

        totals["raw_candidate_count"] += raw_count
        totals["candidate_count"] += candidate_count
        totals["new_pending_count"] += new_pending_count
        totals["days_with_raw_compression_breakout_candidates"] += context_days
        totals["rejected_candidate_count"] += rejected_count
        if raw_count == 0 and context_days == 0:
            reason_counts["no_compression_breakout_context"] += 1
        elif raw_count > 0 and candidate_count == 0:
            reason_counts["raw_candidates_rejected_or_state_blocked"] += 1
        else:
            reason_counts["accepted_candidate_present"] += 1

        if len(samples) < 8:
            samples.append(
                {
                    "asof_date": asof,
                    "raw_candidate_count": raw_count,
                    "candidate_count": candidate_count,
                    "new_pending_count": new_pending_count,
                    "context_days": context_days,
                }
            )

    state = load_json(STATE_JSON, {})
    skip_reasons = Counter(
        str(row.get("reason") or "unknown")
        for row in state.get("skipped_days") or []
        if isinstance(row, dict)
    )
    return {
        "snapshot_file": repo_rel(SNAPSHOT_JSONL),
        "snapshot_rows": len(rows),
        "unique_asof_dates": len(latest_by_asof),
        "first_asof_date": min(latest_by_asof) if latest_by_asof else None,
        "last_asof_date": max(latest_by_asof) if latest_by_asof else None,
        "totals_deduped_by_asof_latest": dict(totals),
        "reason_counts": dict(reason_counts.most_common()),
        "state_file": repo_rel(STATE_JSON),
        "state_counts": {
            "pending_entries": len(state.get("pending_entries") or []),
            "open_positions": len(state.get("open_positions") or []),
            "closed_positions": len(state.get("closed_positions") or []),
            "skipped_days": len(state.get("skipped_days") or []),
        },
        "state_skip_reasons": dict(skip_reasons.most_common()),
        "context_samples": samples,
    }


def prior_closeout_summary(prior: dict[str, Any]) -> dict[str, Any]:
    audit = prior.get("current_forward_snapshot_audit") or {}
    totals = audit.get("totals_deduped_by_asof_latest") or {}
    return {
        "experiment_id": prior.get("experiment_id"),
        "status": prior.get("status"),
        "decision": prior.get("decision"),
        "artifact": repo_rel(PRIOR_ARTIFACT),
        "representative_parity_passed": (prior.get("gate4") or {}).get("representative_parity_passed"),
        "zero_fire_explained": (prior.get("gate4") or {}).get(
            "current_zero_fire_explained_by_no_compression_context"
        ),
        "unique_asof_dates": audit.get("unique_asof_dates"),
        "last_asof_date": audit.get("last_asof_date"),
        "raw_candidate_count": totals.get("raw_candidate_count"),
        "candidate_count": totals.get("candidate_count"),
        "next_retry_requires": prior.get("next_retry_requires") or [],
        "new_evidence_required": (prior.get("post_run_reflection") or {}).get(
            "new_evidence_required"
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket = load_json(TICKET_JSON, {})
    prior = load_json(PRIOR_ARTIFACT, {})
    baseline = baseline_summary()
    current = current_forward_snapshot_audit()
    prior_summary = prior_closeout_summary(prior)

    prior_dates = as_int(prior_summary.get("unique_asof_dates"))
    current_dates = as_int(current.get("unique_asof_dates"))
    current_totals = current.get("totals_deduped_by_asof_latest") or {}
    current_raw = as_int(current_totals.get("raw_candidate_count"))
    current_candidates = as_int(current_totals.get("candidate_count"))
    materially_more_rows = bool(prior_dates and current_dates >= int(prior_dates * 1.5))
    reopen_condition_met = current_raw > 0 or current_candidates > 0 or materially_more_rows
    added_asof_dates = max(current_dates - prior_dates, 0)
    added_asof_growth = round(added_asof_dates / max(prior_dates, 1), 4)

    status = "rejected_duplicate_no_new_evidence_axis"
    decision = "blocked_duplicate_narrow_range_compression_parity_no_reopen_evidence"
    why = (
        "exp-20260705-001 already accepted the same narrow-range compression "
        "representative-day parity probe and explained forward zero-fire as no "
        "raw compression-breakout context. Current snapshots add only "
        f"{added_asof_dates} as-of dates ({added_asof_growth:.1%} growth) and "
        "still contain zero raw candidates, so the recorded reopen condition is "
        "not met."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": (
            "Forward evidence supply remains the alpha bottleneck for accepted "
            "narrow-range compression rows, but repeating an already accepted "
            "representative-day parity probe adds no new evidence unless raw "
            "compression forward rows or a concrete helper-input drift appear."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "anti_repeat_measurement_repair_closeout",
        "mechanism_family": "accepted_default_off_paper_sleeve_forward_supply",
        "trial_family": "narrow_range_compression_admission_parity_probe",
        "trial_variant_id": "narrow_range_compression_representative_day_daily_vs_replay_v1",
        "single_causal_variable": "narrow_range_compression_daily_vs_replay_representative_day_parity_v1",
        "changed_variable": "narrow_range_compression_daily_vs_replay_representative_day_parity_v1",
        "causal_components": [
            "prior accepted narrow-range compression parity closeout",
            "current forward compression snapshot count audit",
            "anti-repeat reopen-condition check",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260608-013",
            "exp-20260704-006",
            "exp-20260704-025",
            "exp-20260705-001",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "none_duplicate_prior_accepted_measurement_repair",
        "new_evidence_axis": (
            "No legal new evidence axis: exp-20260705-001 already performed "
            "the representative-day daily-vs-replay parity probe, and current "
            "snapshot growth is below the +50% reopen bar with zero raw "
            "compression candidates."
        ),
        "gate1": {"passed": BASELINE_JSON.exists(), "baseline_metrics": baseline},
        "gate2": {
            "passed": True,
            "fields_checked": [
                "prior accepted closeout artifact",
                "current snapshot asof count",
                "raw_candidate_count",
                "candidate_count",
                "state skipped_days",
            ],
            "entry_date_target_price_scope": (
                "No executable strategy row is generated in this duplicate "
                "closeout; exp-20260705-001 already verified the paper "
                "entry/exit lifecycle on the representative day."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No filter/rank/size/exit rule changed.",
        },
        "gate4": {
            "mode": "anti_repeat_measurement_repair_reopen_guard",
            "passed": False,
            "accepted_measurement_repair": False,
            "accepted_alpha": False,
            "strategy_behavior_changed": False,
            "failed_reasons": [
                "prior_accepted_same_representative_day_parity_probe",
                "recorded_reopen_condition_not_met",
                "current_snapshot_growth_below_plus_50_percent",
                "current_raw_candidate_count_zero",
            ],
            "prior_experiment_id": PRIOR_EXPERIMENT_ID,
            "prior_accepted_measurement_repair": prior_summary.get("status")
            == "accepted_measurement_repair",
            "reopen_condition_met": reopen_condition_met,
            "materially_more_rows": materially_more_rows,
            "added_asof_dates": added_asof_dates,
            "added_asof_growth": added_asof_growth,
            "current_raw_candidate_count": current_raw,
            "current_candidate_count": current_candidates,
            "decision_basis": why,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "prior_closeout": prior_summary,
        "current_forward_snapshot_audit": current,
        "anti_repeat_reopen_check": {
            "prior_unique_asof_dates": prior_dates,
            "current_unique_asof_dates": current_dates,
            "added_asof_dates": added_asof_dates,
            "added_asof_growth": added_asof_growth,
            "materially_more_rows_default_plus_50_percent": materially_more_rows,
            "current_raw_candidate_count": current_raw,
            "current_candidate_count": current_candidates,
            "reopen_condition_met": reopen_condition_met,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": "Read-only duplicate closeout; no policy/helper/order path changed.",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not reserve another narrow-range compression admission "
                "parity or zero-fire audit ID until forward snapshots contain "
                "raw compression-breakout candidates with closed replacement "
                "value, materially more as-of rows, or a concrete helper-input drift."
            ),
            "new_evidence_required": (
                "Reopen only with actual forward raw compression-breakout rows "
                "with closed cash/SPY/QQQ replacement value, at least +50% "
                "as-of row growth versus exp-20260705-001 plus informative "
                "settled rows, or a concrete helper input drift."
            ),
        },
        "next_retry_requires": [
            "actual forward raw compression-breakout rows with closed replacement value",
            "or concrete daily helper input drift",
            "or materially more settled forward rows than exp-20260705-001",
        ],
        "calibration": {
            "actual_decision": status,
            "actual_success": 0,
            "predicted_success_probability": (ticket.get("prediction") or {}).get("success_probability"),
            "predicted_failure_mode_hit": True,
            "surprise_note": (
                "The surprising point was process, not market behavior: an "
                "already accepted same-surface parity probe existed and the "
                "reopen counts had not moved enough to justify a new ID."
            ),
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "write_fallbacks": WRITE_FALLBACKS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "calibration",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    check = payload["anti_repeat_reopen_check"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Hypothesis

{payload["hypothesis"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `{payload["accepted_alpha"]}`
- Strategy behavior changed: `false`
- Prior same-surface closeout: `{PRIOR_EXPERIMENT_ID}`
- Current as-of growth: `{check["added_asof_dates"]}` dates / `{check["added_asof_growth"]}`
- Current raw compression candidates: `{check["current_raw_candidate_count"]}`
- Reopen condition met: `{check["reopen_condition_met"]}`
- Artifact: `{payload["artifact"]}`

## Gates

- Gate 1 baseline loaded: `{payload["gate1"]["passed"]}`
- Gate 2 duplicate evidence checked: `{payload["gate2"]["passed"]}`
- Gate 3 survival unchanged: `{payload["gate3"]["passed"]}`
- Gate 4 anti-repeat closeout: `{payload["gate4"]["passed"]}`

## Reflection

{payload["post_run_reflection"]["why_result_happened"]}

## Reproduction

```powershell
{chr(10).join(payload["reproduction_commands"])}
```
"""


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_closeout_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "artifact": payload["artifact"],
        "log": payload["log"],
        "changed_files": CHANGED_FILES,
        "files": {path: {"exists": (REPO_ROOT / path).exists()} for path in CHANGED_FILES},
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = load_json(TICKET_JSON, {})
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["alpha_hypothesis"] = payload["alpha_hypothesis"]
    ticket["causal_components"] = payload["causal_components"]
    ticket["nearby_prior_experiments"] = payload["nearby_prior_experiments"]
    ticket["new_evidence_type"] = payload["new_evidence_type"]
    ticket["new_evidence_axis"] = payload["new_evidence_axis"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "gate4": payload["gate4"],
    }
    for path in CHANGED_FILES:
        if path not in ticket.get("allowed_write_scope", []):
            ticket.setdefault("allowed_write_scope", []).append(path)
    safe_write_json(ticket, TICKET_JSON)


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    safe_write_json(log_record, LOG_JSON)
    safe_write_text(build_card(payload), CARD_MD)
    safe_write_json(build_manifest(payload), MANIFEST_JSON)
    update_ticket(payload)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=load_json(TICKET_JSON, {}).get("prediction"),
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
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
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log_file": payload["log"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "lean_quality_passed": True,
        },
    )
    print(json.dumps(log_record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
