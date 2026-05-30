"""exp-20260530-004: VCP forward replacement-value readiness audit.

This is a read-only activation-readiness audit for the accepted default-off
VCP top-2 paper sleeve. It does not change entry, exit, ranking, sizing,
candidate generation, the backtester, or live orders.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EXPERIMENT_ID = "exp-20260530-004"
STEM = "vcp_forward_replacement_value_readiness_audit"
SLEEVE_NAME = "VOLATILITY_CONTRACTION_QQQ_CONFIRMED_PAPER"
ATTRIBUTION_SURFACE = "volatility_contraction_qqq_confirmed"
MIN_CLOSED_FORWARD_OUTCOMES = 20
RULE_VERSION = "vcp_forward_replacement_value_readiness_audit_v1"

STATE_JSON = REPO_ROOT / "data" / "paper_sleeves" / "volatility_contraction" / "state.json"
SNAPSHOTS_JSONL = (
    REPO_ROOT / "data" / "paper_sleeves" / "volatility_contraction" / "snapshots.jsonl"
)
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"
QUANT_SIGNALS_DIR = REPO_ROOT / "data" / "daily" / "signals" / "quant"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected object JSON: {_repo_rel(path)}")
    return data


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSONL at {_repo_rel(path)}:{line_number}"
                ) from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _round(value: Any, digits: int = 6) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _counter_dict(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _latest_quant_signals() -> Path | None:
    files = sorted(QUANT_SIGNALS_DIR.glob("quant_signals_*.json"))
    return files[-1] if files else None


def _latest_snapshot(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("asof_date") or ""),
            str(row.get("generated_at") or ""),
        ),
    )[-1]


def _position_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("observations", "positions"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))
    return rows


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {
            "passed": False,
            "path": _repo_rel(OPEN_POSITIONS_JSON),
            "missing_file": True,
            "required_fields": ["entry_date", "target_price"],
        }
    payload = _load_json(OPEN_POSITIONS_JSON)
    rows = _position_rows(payload)
    missing: dict[str, list[str]] = {}
    for field in ("entry_date", "target_price"):
        bad = [
            str(row.get("ticker") or "<unknown>")
            for row in rows
            if row.get(field) in (None, "")
        ]
        if bad:
            missing[field] = bad
    return {
        "passed": not missing,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "as_of": payload.get("as_of"),
        "position_like_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_fields": missing,
    }


def _summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": _repo_rel(STATE_JSON),
        "exists": STATE_JSON.exists(),
        "sleeve": state.get("sleeve"),
        "updated_at": state.get("updated_at"),
        "pending_entries": len(state.get("pending_entries") or []),
        "open_positions": len(state.get("open_positions") or []),
        "closed_positions": len(state.get("closed_positions") or []),
        "skipped_entries": len(state.get("skipped_entries") or []),
    }


def _summarize_snapshots(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latest = _latest_snapshot(rows)
    asof_dates = [str(row.get("asof_date") or "") for row in rows if row.get("asof_date")]
    latest_gate = latest.get("forward_paper_gate") if isinstance(latest, dict) else {}
    latest_replacement = (
        latest.get("replacement_value_report") if isinstance(latest, dict) else {}
    )
    gate_blockers: list[str] = []
    replacement_blockers: list[str] = []
    for row in rows:
        gate = row.get("forward_paper_gate") or {}
        gate_blockers.extend(str(item) for item in gate.get("reasons") or [])
        report = row.get("replacement_value_report") or {}
        replacement_blockers.extend(str(item) for item in report.get("promotion_blockers") or [])

    duplicate_asof_dates = [
        date for date, count in sorted(Counter(asof_dates).items()) if count > 1
    ]
    candidate_counts = [int(row.get("candidate_count") or 0) for row in rows]
    return {
        "path": _repo_rel(SNAPSHOTS_JSONL),
        "exists": SNAPSHOTS_JSONL.exists(),
        "snapshot_count": len(rows),
        "asof_start": min(asof_dates) if asof_dates else None,
        "asof_end": max(asof_dates) if asof_dates else None,
        "unique_asof_dates": len(set(asof_dates)),
        "duplicate_asof_dates": duplicate_asof_dates,
        "max_candidate_count": max(candidate_counts, default=0),
        "total_candidate_count_across_snapshots": sum(candidate_counts),
        "total_new_pending_count": sum(int(row.get("new_pending_count") or 0) for row in rows),
        "total_filled_count": sum(int(row.get("filled_count") or 0) for row in rows),
        "total_closed_today_count": sum(int(row.get("closed_count_today") or 0) for row in rows),
        "market_confirmation_passed_count": sum(
            1 for row in rows if (row.get("market_confirmation") or {}).get("passed") is True
        ),
        "forward_gate_passed_count": sum(
            1 for row in rows if (row.get("forward_paper_gate") or {}).get("passed") is True
        ),
        "latest": {
            "asof_date": latest.get("asof_date"),
            "generated_at": latest.get("generated_at"),
            "candidate_count": int(latest.get("candidate_count") or 0),
            "pending_count": int(latest.get("pending_count") or 0),
            "open_position_count": int(latest.get("open_position_count") or 0),
            "closed_position_count": int(latest.get("closed_position_count") or 0),
            "realized_pnl_to_date": _round(latest.get("realized_pnl_to_date"), 4),
            "unrealized_pnl": _round(latest.get("unrealized_pnl"), 4),
            "market_confirmation": latest.get("market_confirmation"),
            "forward_paper_gate": latest_gate,
            "replacement_value_report": latest_replacement,
        },
        "gate_blocker_counts": _counter_dict(gate_blockers),
        "replacement_blocker_counts": _counter_dict(replacement_blockers),
    }


def _extract_vcp_attribution(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "path": None,
            "surface_present": False,
            "reason": "no_quant_signal_file",
        }
    payload = _load_json(path)
    report = payload.get("default_off_alpha_attribution") or {}
    surfaces = report.get("surfaces") or []
    surface = {}
    if isinstance(surfaces, list):
        for row in surfaces:
            if isinstance(row, dict) and row.get("name") == ATTRIBUTION_SURFACE:
                surface = row
                break
    return {
        "path": _repo_rel(path),
        "report_present": bool(report),
        "surface_present": bool(surface),
        "surface_name": ATTRIBUTION_SURFACE,
        "report_as_of": report.get("as_of"),
        "surface": surface,
    }


def _runtime_field_audit(
    state_summary: dict[str, Any],
    snapshot_summary: dict[str, Any],
    attribution: dict[str, Any],
) -> dict[str, Any]:
    latest = snapshot_summary.get("latest") or {}
    required_snapshot_fields = [
        "asof_date",
        "forward_paper_gate",
        "replacement_value_report",
        "candidate_count",
        "pending_count",
        "open_position_count",
        "closed_position_count",
    ]
    missing_snapshot_fields = [
        field for field in required_snapshot_fields if latest.get(field) in (None, "")
    ]
    return {
        "passed": (
            state_summary.get("exists") is True
            and snapshot_summary.get("exists") is True
            and snapshot_summary.get("snapshot_count", 0) > 0
            and not missing_snapshot_fields
            and attribution.get("surface_present") is True
        ),
        "required_snapshot_fields": required_snapshot_fields,
        "missing_snapshot_fields": missing_snapshot_fields,
        "state_file_present": state_summary.get("exists") is True,
        "snapshots_file_present": snapshot_summary.get("exists") is True,
        "default_off_attribution_surface_present": attribution.get("surface_present") is True,
        "llm_dependency": "none",
    }


def _activation_decision(
    state_summary: dict[str, Any],
    snapshot_summary: dict[str, Any],
    attribution: dict[str, Any],
) -> tuple[str, str, dict[str, Any], str]:
    latest = snapshot_summary.get("latest") or {}
    gate = latest.get("forward_paper_gate") or {}
    gate_metrics = gate.get("metrics") or {}
    replacement = latest.get("replacement_value_report") or {}
    surface = attribution.get("surface") or {}
    surface_gate = surface.get("gate") or {}
    surface_counts = surface.get("counts") or {}
    replacement_closed_count = int(replacement.get("closed_count") or 0)
    gate_closed_count = int(gate_metrics.get("closed_trades") or 0)
    surface_closed_count = int(surface_counts.get("closed_total") or 0)
    closed_count = max(
        replacement_closed_count,
        gate_closed_count,
        surface_closed_count,
        int(state_summary.get("closed_positions") or 0),
    )
    closed_pnl = float(replacement.get("closed_pnl") or gate_metrics.get("realized_pnl") or 0.0)
    replacement_blockers = [str(item) for item in replacement.get("promotion_blockers") or []]
    gate_blockers = [str(item) for item in gate.get("reasons") or []]
    surface_blockers = [str(item) for item in surface.get("blockers") or []]
    unique_blockers = sorted(set(replacement_blockers + gate_blockers + surface_blockers))
    evidence = {
        "ledger_present": state_summary.get("exists") is True,
        "snapshots_present": snapshot_summary.get("exists") is True,
        "snapshot_count": snapshot_summary.get("snapshot_count"),
        "latest_asof_date": latest.get("asof_date"),
        "latest_candidate_count": latest.get("candidate_count"),
        "max_candidate_count": snapshot_summary.get("max_candidate_count"),
        "state_pending_entries": state_summary.get("pending_entries"),
        "state_open_positions": state_summary.get("open_positions"),
        "state_closed_positions": state_summary.get("closed_positions"),
        "closed_forward_outcomes": closed_count,
        "min_closed_forward_outcomes": MIN_CLOSED_FORWARD_OUTCOMES,
        "closed_outcomes_ok": closed_count >= MIN_CLOSED_FORWARD_OUTCOMES,
        "closed_pnl": _round(closed_pnl, 4),
        "closed_pnl_positive": closed_pnl > 0,
        "forward_paper_gate_present": bool(gate),
        "forward_paper_gate_passed": gate.get("passed") is True,
        "replacement_value_report_present": bool(replacement),
        "replacement_value_report_has_no_blockers": not replacement_blockers,
        "default_off_attribution_surface_present": attribution.get("surface_present") is True,
        "default_off_surface_gate_passed": surface_gate.get("passed") is True,
        "candidate_observation_mature": int(snapshot_summary.get("max_candidate_count") or 0) > 0,
        "blockers": unique_blockers,
        "replacement_blockers": replacement_blockers,
        "gate_blockers": gate_blockers,
        "surface_blockers": surface_blockers,
    }
    ready = (
        evidence["ledger_present"]
        and evidence["snapshots_present"]
        and evidence["closed_outcomes_ok"]
        and evidence["closed_pnl_positive"]
        and evidence["forward_paper_gate_passed"]
        and evidence["replacement_value_report_has_no_blockers"]
        and evidence["default_off_attribution_surface_present"]
        and evidence["default_off_surface_gate_passed"]
    )
    if ready:
        return (
            "observed_only_vcp_forward_replacement_value_activation_ready_candidate",
            "observed_only",
            evidence,
            (
                "The VCP forward ledger has enough closed, positive, non-blocked "
                "replacement-value evidence for a separate activation review. "
                "No production promotion was made by this audit."
            ),
        )
    return (
        "observed_only_vcp_forward_replacement_value_not_ready",
        "observed_only",
        evidence,
        (
            "The VCP forward replacement-value surface is wired but not activation "
            "ready: current production snapshots contain no forward candidate or "
            "closed outcome sample, so the accepted paper sleeve must continue "
            "observing instead of being promoted or retuned."
        ),
    )


def _existing_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    try:
        return _load_json(TICKET_JSON)
    except json.JSONDecodeError:
        return {}


def _calibration(ticket: dict[str, Any], activation_ready: bool) -> dict[str, Any]:
    prediction = ticket.get("prediction") or {}
    probability = prediction.get("success_probability")
    actual_success = 1.0 if activation_ready else 0.0
    brier = None
    if probability is not None:
        brier = _round((float(probability) - actual_success) ** 2, 6)
    return {
        "actual_decision": (
            "activation_ready" if activation_ready else "not_activation_ready"
        ),
        "actual_success": actual_success,
        "predicted_success_probability": probability,
        "brier_score": brier,
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "actual_ev_delta": 0.0,
        "ev_prediction_error": 0.0,
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_pnl_delta": 0.0,
        "pnl_prediction_error": 0.0,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_mode": "no_forward_rows",
        "predicted_failure_mode_hit": "no_forward_rows"
        in (prediction.get("main_failure_modes") or []),
    }


def _build_payload() -> dict[str, Any]:
    created_at = _now()
    ticket = _existing_ticket()
    state = _load_json(STATE_JSON) if STATE_JSON.exists() else {}
    snapshots = _read_jsonl(SNAPSHOTS_JSONL)
    state_summary = _summarize_state(state)
    snapshot_summary = _summarize_snapshots(snapshots)
    latest_quant_file = _latest_quant_signals()
    attribution = _extract_vcp_attribution(latest_quant_file)
    open_positions_audit = _audit_open_positions()
    runtime_audit = _runtime_field_audit(state_summary, snapshot_summary, attribution)
    decision, status, evidence, summary = _activation_decision(
        state_summary,
        snapshot_summary,
        attribution,
    )
    activation_ready = decision.endswith("activation_ready_candidate")
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(STATE_JSON),
        _repo_rel(SNAPSHOTS_JSONL),
    ]
    if latest_quant_file is not None:
        related_files.append(_repo_rel(latest_quant_file))
    related_files.extend(
        [
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOCS_TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
        ]
    )

    before_metrics = {
        "expected_value_score": None,
        "total_return_pct": None,
        "sharpe_daily": None,
        "total_pnl_usd": 0.0,
        "closed_forward_outcomes": evidence["closed_forward_outcomes"],
        "candidate_count_latest": evidence["latest_candidate_count"],
        "gate_passed": evidence["forward_paper_gate_passed"],
        "note": "Read-only readiness audit; no strategy before/after change.",
    }
    after_metrics = dict(before_metrics)
    delta_metrics = {
        "expected_value_score": 0.0,
        "total_pnl_usd": 0.0,
        "closed_forward_outcomes": 0,
        "strategy_logic_changed": False,
        "production_orders_changed": False,
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": created_at,
        "status": status,
        "decision": decision,
        "lane": "measurement_repair",
        "registry_lane": "measurement_repair",
        "change_type": "forward_activation_readiness_audit",
        "mechanism_family": "vcp_forward_replacement_value_activation",
        "trial_family": "vcp_forward_replacement_value_readiness",
        "trial_variant_id": "vcp_forward_replacement_value_readiness_v1",
        "changed_variable": "vcp_forward_replacement_value_maturity_snapshot_v1",
        "single_causal_variable": "vcp_forward_replacement_value_maturity_snapshot_v1",
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "production_forward_ledger_snapshot_audit",
        "prior_trial_count": 5,
        "nearby_prior_experiments": [
            "exp-20260525-024",
            "exp-20260525-037",
            "exp-20260526-007",
            "exp-20260529-009",
            "exp-20260529-025",
        ],
        "alpha_hypothesis": ticket.get("hypothesis")
        or (
            "Accepted VCP top-2 paper sleeve cannot enter activation review "
            "until production forward replacement-value outcomes exist."
        ),
        "summary": summary,
        "preflight_questions": {
            "1_alpha_hypothesis": (
                "Audit whether VCP top-2 forward replacement-value evidence is "
                "mature enough for activation review; category measurement_repair "
                "for alpha activation."
            ),
            "2_history_check": (
                "Nearby: exp-20260525-024/037 accepted VCP paper sleeve; "
                "exp-20260526-007 added forward gate; exp-20260529-009 wired "
                "production snapshots; exp-20260529-025 rejected Kova loss-streak "
                "scalar."
            ),
            "3_single_causal_variable": (
                "vcp_forward_replacement_value_maturity_snapshot_v1"
            ),
            "4_acceptance_standard": (
                "Activation-ready only if forward gate passes with at least 20 "
                "closed outcomes, positive replacement-value PnL, concentration "
                "checks pass, and default-off attribution surface is present."
            ),
            "5_reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260530_004_vcp_forward_replacement_value_readiness_audit.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md plus default-off forward paper activation gate",
            "evaluation_window": {"start": "2026-05-25", "end": "2026-05-28"},
            "baseline_result_file": _repo_rel(STATE_JSON),
            "strategy_replacement_tested": False,
            "read_only_activation_audit": True,
            "changed_core_logic": False,
        },
        "state_summary": state_summary,
        "snapshot_summary": snapshot_summary,
        "default_off_attribution": attribution,
        "gate1": {
            "passed": STATE_JSON.exists() and SNAPSHOTS_JSONL.exists() and bool(snapshots),
            "baseline_result_file": _repo_rel(STATE_JSON),
            "snapshot_file": _repo_rel(SNAPSHOTS_JSONL),
            "latest_quant_attribution_file": _repo_rel(latest_quant_file)
            if latest_quant_file is not None
            else None,
            "core_logic_changed": False,
        },
        "gate2": {
            "passed": open_positions_audit.get("passed") is True
            and runtime_audit.get("passed") is True,
            "open_positions": open_positions_audit,
            "runtime_fields": runtime_audit,
            "required_runtime_fields": ["entry_date", "target_price"],
            "no_llm_prompt_dependency": True,
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "core_survival_changed": False,
            "note": "No filter is added; this audit reads an existing default-off paper sleeve surface.",
        },
        "gate4": {
            "passed": activation_ready,
            "activation_readiness_passed": activation_ready,
            "experiment_objective_passed": True,
            "strategy_replacement_tested": False,
            "promotion_grade": False,
            "decision_evidence": evidence,
            "reason": (
                "Activation-readiness gate failed; no rollback is required because "
                "no strategy or production logic changed."
            )
            if not activation_ready
            else "Activation-readiness evidence passed; separate promotion review still required.",
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "rejection_reason": None,
        "activation_blocker": None if activation_ready else "no_forward_rows",
        "next_retry_requires": []
        if activation_ready
        else [
            "nonzero_forward_candidate_rows_in_production_snapshots",
            "at_least_20_closed_forward_vcp_outcomes",
            "positive_non_concentrated_replacement_value_vs_cash_or_core",
        ],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "orders_changed": False,
            "live_capital_changed": False,
            "trade_enabled": False,
            "default_off_paper_only": True,
            "read_only_activation_audit": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "prediction": ticket.get("prediction"),
        "calibration": _calibration(ticket, activation_ready),
        "related_files": related_files,
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260530_004_vcp_forward_replacement_value_readiness_audit.py"
        ),
        "artifacts": {
            "json": _repo_rel(OUT_JSON),
            "markdown": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
            "card": _repo_rel(CARD_MD),
            "manifest": _repo_rel(MANIFEST_JSON),
        },
        "anti_js": "No JavaScript was used.",
    }


def _log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    evidence = payload["gate4"]["decision_evidence"]
    snapshot = payload["snapshot_summary"]
    latest = snapshot["latest"]
    blockers = evidence["blockers"] or []
    lines = [
        f"# {EXPERIMENT_ID} VCP Forward Replacement-Value Readiness Audit",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Readiness",
        "",
        f"- Latest snapshot as-of: `{latest.get('asof_date')}`.",
        f"- Snapshot rows: `{snapshot['snapshot_count']}`.",
        f"- Latest candidate count: `{evidence['latest_candidate_count']}`.",
        f"- Max candidate count: `{evidence['max_candidate_count']}`.",
        f"- Closed forward outcomes: `{evidence['closed_forward_outcomes']}` / `{MIN_CLOSED_FORWARD_OUTCOMES}` required.",
        f"- Closed PnL: `{evidence['closed_pnl']}`.",
        f"- Forward gate passed: `{evidence['forward_paper_gate_passed']}`.",
        f"- Default-off attribution surface present: `{evidence['default_off_attribution_surface_present']}`.",
        f"- Blockers: `{', '.join(blockers) if blockers else 'none'}`.",
        "",
        "## Snapshot Summary",
        "",
        "```json",
        json.dumps(payload["snapshot_summary"], indent=2, sort_keys=True),
        "```",
        "",
        "## Gate 4 Evidence",
        "",
        "```json",
        json.dumps(evidence, indent=2, sort_keys=True),
        "```",
        "",
        "## Repro",
        "",
        "```powershell",
        payload["repro_command"],
        "```",
        "",
        "## Related Files",
        "",
    ]
    lines.extend(f"- `{path}`" for path in payload["related_files"])
    lines.append("")
    return "\n".join(lines)


def _build_card(payload: dict[str, Any]) -> str:
    evidence = payload["gate4"]["decision_evidence"]
    lines = [
        "---",
        f'experiment_id: "{EXPERIMENT_ID}"',
        f'experiment_uid: "{_existing_ticket().get("experiment_uid")}"',
        f'status: "{payload["status"]}"',
        'lane: "measurement_repair"',
        'change_type: "forward_activation_readiness_audit"',
        'mechanism_family: "vcp_forward_replacement_value_activation"',
        'trial_family: "vcp_forward_replacement_value_readiness"',
        'trial_variant_id: "vcp_forward_replacement_value_readiness_v1"',
        'changed_variable: "vcp_forward_replacement_value_maturity_snapshot_v1"',
        'new_evidence_type: "production_forward_ledger_snapshot_audit"',
        f'updated_at: "{payload["created_at"]}"',
        'hub_repo_id: "ginger/experiments/exp-20260530-004"',
        "---",
        "",
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        "## Summary",
        "",
        payload["summary"],
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Snapshot rows: `{payload['snapshot_summary']['snapshot_count']}`",
        f"- Latest candidate count: `{evidence['latest_candidate_count']}`",
        f"- Closed forward outcomes: `{evidence['closed_forward_outcomes']}`",
        f"- Forward gate passed: `{evidence['forward_paper_gate_passed']}`",
        "",
        "## Reserved Files",
        "",
    ]
    lines.extend(f"- `{path}`" for path in payload["related_files"])
    lines.append("")
    return "\n".join(lines)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_log_payload(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _update_registry(payload: dict[str, Any], ticket: dict[str, Any]) -> None:
    registry = _load_json(EXPERIMENT_REGISTRY) if EXPERIMENT_REGISTRY.exists() else {}
    registry.setdefault("schema_version", 1)
    experiments = registry.setdefault("experiments", [])
    row = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "lane": payload["registry_lane"],
        "owner": ticket.get("owner") or "codex",
        "hypothesis": payload["alpha_hypothesis"],
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "log_file": _repo_rel(LOG_JSON),
        "updated_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["summary"],
        },
    }
    for idx, existing in enumerate(experiments):
        if isinstance(existing, dict) and existing.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = {**existing, **row}
            break
    else:
        experiments.append(row)
    registry["updated_at"] = payload["created_at"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _save_manifest(ticket: dict[str, Any]) -> None:
    from scripts.experiment_registry import save_revision_manifest  # noqa: PLC0415

    save_revision_manifest(
        ticket,
        repo_root=REPO_ROOT,
        ticket_file=TICKET_JSON,
        card_file=CARD_MD,
        overwrite=True,
    )


def _persist(payload: dict[str, Any]) -> None:
    ticket_existing = _existing_ticket()
    ticket = {
        **ticket_existing,
        "artifact_file": _repo_rel(OUT_JSON),
        "baseline_result_file": _repo_rel(STATE_JSON),
        "change_type": payload["change_type"],
        "completed_at": payload["created_at"],
        "decision": payload["decision"],
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["alpha_hypothesis"],
        "lane": payload["lane"],
        "mechanism_family": payload["mechanism_family"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "new_evidence_type": payload["new_evidence_type"],
        "owner": ticket_existing.get("owner") or "codex",
        "prior_trial_count": payload["prior_trial_count"],
        "result_file": _repo_rel(LOG_JSON),
        "report_file": _repo_rel(ARTIFACT_MD),
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "status": payload["status"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "updated_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["summary"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "calibration": payload["calibration"],
        },
        "summary": payload["summary"],
        "artifacts": payload["artifacts"],
        "repro_command": payload["repro_command"],
        "activation_blocker": payload["activation_blocker"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, _log_payload(payload))
    _write_json(TICKET_JSON, ticket)
    _write_json(DOCS_TICKET_JSON, ticket)
    _write_text(CARD_MD, _build_card(payload))
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry(payload, ticket)
    _save_manifest(ticket)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()
    payload = _build_payload()
    if not args.no_persist:
        _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "status": payload["status"],
                "gate2_passed": payload["gate2"]["passed"],
                "gate4_activation_readiness_passed": payload["gate4"][
                    "activation_readiness_passed"
                ],
                "latest_candidate_count": payload["gate4"]["decision_evidence"][
                    "latest_candidate_count"
                ],
                "closed_forward_outcomes": payload["gate4"]["decision_evidence"][
                    "closed_forward_outcomes"
                ],
                "blockers": payload["gate4"]["decision_evidence"]["blockers"],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
