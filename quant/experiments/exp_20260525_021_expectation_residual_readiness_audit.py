"""exp-20260525-021: expectation x residual readiness audit.

Read-only measurement repair for the expectation drift x residual leadership
research direction. This audit explains whether the existing attribution
experiment has enough PIT estimate-revision, residual-strength, and forward
outcome coverage to be interpreted.

It does not alter signal generation, ranking, sizing, exits, LLM/news, or
orders.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260525-021"
STEM = "expectation_residual_readiness_audit"
MECHANISM_FAMILY = "expectation_residual_leadership"
TRIAL_FAMILY = "expectation_residual_readiness_audit"
CHANGED_VARIABLE = "expectation_residual_readiness_audit_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from exp_20260525_017_expectation_residual_leadership_attribution import (  # noqa: E402
    FORWARD_HORIZONS,
    MAX_SINGLE_TICKER_POSITIVE_SHARE,
    MAX_TOP5_POSITIVE_SHARE,
    MIN_BUCKET_A_5D_OUTCOMES,
    MIN_TOTAL_USABLE_CANDIDATES,
    RESIDUAL_LEADER_STATES,
    _float,
    _open_position_field_check,
    _repo_rel,
    _safe,
    _utc_now,
    _write_json,
    annotate_candidates,
    build_price_lookup,
    classify_bucket,
    load_candidates,
    load_ledger_map,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

BUCKET_A = "A_positive_expectation_and_residual_leader"
BUCKETS = (
    BUCKET_A,
    "B_positive_expectation_only",
    "C_residual_leader_only",
    "D_neither",
)
RERUN_COMMAND = (
    ".\\.venv\\Scripts\\python.exe -B "
    "quant\\experiments\\exp_20260525_017_expectation_residual_leadership_attribution.py"
)


def _horizon_key(horizon: int) -> str:
    return f"{horizon}d"


def production_impact() -> dict[str, bool]:
    return {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": False,
        "parity_test_added": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }


def _expectation_blocker(row: dict[str, Any]) -> str | None:
    if row.get("expectation_positive"):
        return None
    coverage_gap = row.get("expectation_coverage_gap")
    if coverage_gap:
        return str(coverage_gap)

    status = row.get("expectation_join_status")
    if status in {
        "missing_ledger_row",
        "ledger_row_not_usable",
        "usable_ledger_missing_7d_delta",
    }:
        return str(status)

    delta_7d = _float(row.get("eps_estimate_delta_7d"), None)
    if status == "usable_ledger_with_7d_delta" and delta_7d is not None and delta_7d <= 0:
        return "non_positive_eps_estimate_delta_7d"
    return "no_positive_expectation"


def _residual_blocker(row: dict[str, Any]) -> str | None:
    if row.get("residual_leader"):
        return None
    status = row.get("residual_context_status")
    if status != "ok":
        return str(status or "missing_residual_context_status")
    state = row.get("residual_state") or "unknown"
    return f"not_residual_leader_{state}"


def _forward_gap(row: dict[str, Any], horizon_key: str) -> str | None:
    outcome = (row.get("forward_outcomes") or {}).get(horizon_key) or {}
    if outcome.get("closed") is True:
        return None
    return str(outcome.get("gap_reason") or f"missing_{horizon_key}_forward_outcome")


def bucket_a_readiness_blockers(row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expectation = _expectation_blocker(row)
    if expectation:
        blockers.append(f"expectation:{expectation}")

    residual = _residual_blocker(row)
    if residual:
        blockers.append(f"residual:{residual}")

    forward_5d = _forward_gap(row, "5d")
    if forward_5d:
        blockers.append(f"forward_5d:{forward_5d}")

    return blockers


def _closed_count(rows: list[dict[str, Any]], horizon_key: str) -> int:
    return sum(
        1
        for row in rows
        if ((row.get("forward_outcomes") or {}).get(horizon_key) or {}).get("closed") is True
    )


def _gap_reason_counts(rows: list[dict[str, Any]], horizon_key: str) -> dict[str, int]:
    return dict(
        Counter(
            _forward_gap(row, horizon_key)
            for row in rows
            if _forward_gap(row, horizon_key)
        )
    )


def _bucket_for_row(row: dict[str, Any]) -> str:
    return classify_bucket(
        bool(row.get("expectation_positive")),
        bool(row.get("residual_leader")),
    )


def _daily_candidate_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[str(row.get("as_of_date"))].append(row)

    daily = {}
    for as_of, items in sorted(by_date.items()):
        bucket_counts = Counter(_bucket_for_row(row) for row in items)
        daily[as_of] = {
            "candidate_count": len(items),
            "candidate_source_breakdown": dict(Counter(row.get("candidate_source") for row in items)),
            "ledger_joined_candidates": sum(1 for row in items if row.get("ledger_joined")),
            "ledger_usable_candidates": sum(1 for row in items if row.get("ledger_usable")),
            "eps_estimate_delta_7d_available": sum(
                1 for row in items if row.get("eps_estimate_delta_7d") is not None
            ),
            "positive_expectation_candidates": sum(
                1 for row in items if row.get("expectation_positive")
            ),
            "residual_context_ok_candidates": sum(
                1 for row in items if row.get("residual_context_status") == "ok"
            ),
            "residual_leader_candidates": sum(1 for row in items if row.get("residual_leader")),
            "bucket_counts": {bucket: bucket_counts.get(bucket, 0) for bucket in BUCKETS},
            "forward_close_availability": {
                _horizon_key(horizon): {
                    "closed": _closed_count(items, _horizon_key(horizon)),
                    "missing": len(items) - _closed_count(items, _horizon_key(horizon)),
                    "gap_reason_counts": _gap_reason_counts(items, _horizon_key(horizon)),
                }
                for horizon in FORWARD_HORIZONS
            },
        }
    return daily


def _bucket_readiness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for bucket in BUCKETS:
        items = [row for row in rows if _bucket_for_row(row) == bucket]
        blocker_counter = Counter()
        for row in items:
            blockers = bucket_a_readiness_blockers(row)
            if blockers:
                blocker_counter.update(blockers)
        out[bucket] = {
            "candidate_count": len(items),
            "ticker_count": len({row.get("ticker") for row in items if row.get("ticker")}),
            "ledger_joined_candidates": sum(1 for row in items if row.get("ledger_joined")),
            "ledger_usable_candidates": sum(1 for row in items if row.get("ledger_usable")),
            "eps_estimate_delta_7d_available": sum(
                1 for row in items if row.get("eps_estimate_delta_7d") is not None
            ),
            "eps_estimate_delta_30d_available": sum(
                1 for row in items if row.get("eps_estimate_delta_30d") is not None
            ),
            "positive_expectation_candidates": sum(
                1 for row in items if row.get("expectation_positive")
            ),
            "residual_context_ok_candidates": sum(
                1 for row in items if row.get("residual_context_status") == "ok"
            ),
            "residual_leader_candidates": sum(1 for row in items if row.get("residual_leader")),
            "candidate_source_breakdown": dict(Counter(row.get("candidate_source") for row in items)),
            "record_type_breakdown": dict(Counter(row.get("record_type") for row in items)),
            "forward_close_availability": {
                _horizon_key(horizon): {
                    "closed": _closed_count(items, _horizon_key(horizon)),
                    "missing": len(items) - _closed_count(items, _horizon_key(horizon)),
                    "gap_reason_counts": _gap_reason_counts(items, _horizon_key(horizon)),
                }
                for horizon in FORWARD_HORIZONS
            },
            "bucket_a_readiness_blocking_reason_counts": dict(blocker_counter),
        }
    return out


def _candidate_readiness_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        bucket = _bucket_for_row(row)
        blockers = bucket_a_readiness_blockers(row)
        out.append(
            {
                "as_of_date": row.get("as_of_date"),
                "ticker": row.get("ticker"),
                "candidate_source": row.get("candidate_source"),
                "record_type": row.get("record_type"),
                "selected_signal": row.get("selected_signal"),
                "strategy": row.get("strategy"),
                "bucket": bucket,
                "bucket_a_5d_ready": bucket == BUCKET_A and not blockers,
                "bucket_a_readiness_blockers": blockers,
                "expectation_positive": row.get("expectation_positive"),
                "expectation_join_status": row.get("expectation_join_status"),
                "expectation_coverage_gap": row.get("expectation_coverage_gap"),
                "ledger_joined": row.get("ledger_joined"),
                "ledger_usable": row.get("ledger_usable"),
                "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
                "eps_estimate_delta_30d": row.get("eps_estimate_delta_30d"),
                "residual_leader": row.get("residual_leader"),
                "residual_context_status": row.get("residual_context_status"),
                "residual_state": row.get("residual_state"),
                "residual_strength_score": row.get("residual_strength_score"),
                "forward_close_availability": {
                    _horizon_key(horizon): (
                        (row.get("forward_outcomes") or {}).get(_horizon_key(horizon)) or {}
                    ).get("closed", False)
                    for horizon in FORWARD_HORIZONS
                },
                "forward_gap_reasons": {
                    _horizon_key(horizon): _forward_gap(row, _horizon_key(horizon))
                    for horizon in FORWARD_HORIZONS
                },
            }
        )
    return out


def build_readiness_summary(annotated: list[dict[str, Any]]) -> dict[str, Any]:
    bucket_counts = Counter(_bucket_for_row(row) for row in annotated)
    all_blockers = Counter()
    for row in annotated:
        blockers = bucket_a_readiness_blockers(row)
        if blockers:
            all_blockers.update(blockers)

    forward_close_availability = {
        _horizon_key(horizon): {
            "closed": _closed_count(annotated, _horizon_key(horizon)),
            "missing": len(annotated) - _closed_count(annotated, _horizon_key(horizon)),
            "gap_reason_counts": _gap_reason_counts(annotated, _horizon_key(horizon)),
        }
        for horizon in FORWARD_HORIZONS
    }

    return {
        "candidate_objects_total": len(annotated),
        "candidate_source_breakdown": dict(Counter(row.get("candidate_source") for row in annotated)),
        "record_type_breakdown": dict(Counter(row.get("record_type") for row in annotated)),
        "daily_candidate_coverage": _daily_candidate_coverage(annotated),
        "estimate_revision_ledger_join_coverage": {
            "ledger_joined_candidates": sum(1 for row in annotated if row.get("ledger_joined")),
            "ledger_usable_candidates": sum(1 for row in annotated if row.get("ledger_usable")),
            "expectation_join_status_counts": dict(
                Counter(row.get("expectation_join_status") for row in annotated)
            ),
            "positive_expectation_candidates": sum(
                1 for row in annotated if row.get("expectation_positive")
            ),
        },
        "estimate_revision_delta_availability": {
            "eps_estimate_delta_7d_available": sum(
                1 for row in annotated if row.get("eps_estimate_delta_7d") is not None
            ),
            "eps_estimate_delta_30d_available": sum(
                1 for row in annotated if row.get("eps_estimate_delta_30d") is not None
            ),
        },
        "residual_context_coverage": {
            "residual_context_ok_candidates": sum(
                1 for row in annotated if row.get("residual_context_status") == "ok"
            ),
            "residual_leader_candidates": sum(1 for row in annotated if row.get("residual_leader")),
            "residual_context_status_counts": dict(
                Counter(row.get("residual_context_status") for row in annotated)
            ),
            "residual_leader_states": sorted(RESIDUAL_LEADER_STATES),
        },
        "forward_close_availability": forward_close_availability,
        "bucket_readiness": _bucket_readiness(annotated),
        "bucket_counts": {bucket: bucket_counts.get(bucket, 0) for bucket in BUCKETS},
        "bucket_a_readiness_blocking_reason_counts": dict(all_blockers),
        "candidate_readiness_rows": _candidate_readiness_rows(annotated),
    }


def evaluate_readiness_gate(summary: dict[str, Any]) -> dict[str, Any]:
    bucket_a = summary["bucket_readiness"][BUCKET_A]
    bucket_a_closed_5d = bucket_a["forward_close_availability"]["5d"]["closed"]
    total_5d_closed = summary["forward_close_availability"]["5d"]["closed"]
    data_gap_reasons = []
    if bucket_a_closed_5d < MIN_BUCKET_A_5D_OUTCOMES:
        data_gap_reasons.append("bucket_a_closed_5d_outcomes")
    if total_5d_closed < MIN_TOTAL_USABLE_CANDIDATES:
        data_gap_reasons.append("total_usable_candidates")

    passed = not data_gap_reasons
    return {
        "passed": passed,
        "decision": (
            "ready_to_rerun_expectation_residual_attribution"
            if passed
            else "observed_only_data_gap"
        ),
        "reason": "coverage_ready" if passed else "insufficient_bucket_or_total_sample",
        "data_gap_reasons": data_gap_reasons,
        "bucket_a_closed_5d_outcomes": bucket_a_closed_5d,
        "minimum_bucket_a_closed_5d_outcomes": MIN_BUCKET_A_5D_OUTCOMES,
        "total_usable_candidates": total_5d_closed,
        "minimum_total_usable_candidates": MIN_TOTAL_USABLE_CANDIDATES,
        "ready_to_rerun_attribution": passed,
        "exact_rerun_command": RERUN_COMMAND,
        "interpretation_rule": (
            "Only rerun and interpret exp-20260525-017 when this readiness gate passes."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    summary = payload["readiness_summary"]
    gate = payload["readiness_gate"]
    lines = [
        f"# {EXPERIMENT_ID} Expectation Residual Readiness Audit",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Read-only measurement repair. No entries, exits, ranking, sizing, LLM/news, or orders changed.",
        "",
        "## Readiness Gate",
        "",
        "```json",
        json.dumps(gate, indent=2, sort_keys=True),
        "```",
        "",
        "## Coverage",
        "",
        "```json",
        json.dumps(
            {
                "candidate_objects_total": summary["candidate_objects_total"],
                "bucket_counts": summary["bucket_counts"],
                "estimate_revision_ledger_join_coverage": summary[
                    "estimate_revision_ledger_join_coverage"
                ],
                "estimate_revision_delta_availability": summary[
                    "estimate_revision_delta_availability"
                ],
                "residual_context_coverage": summary["residual_context_coverage"],
                "forward_close_availability": summary["forward_close_availability"],
                "bucket_a_readiness_blocking_reason_counts": summary[
                    "bucket_a_readiness_blocking_reason_counts"
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        "```",
        "",
        "## Rerun Command",
        "",
        "```powershell",
        RERUN_COMMAND,
        "```",
        "",
        "No JavaScript was used.",
        "",
    ]
    return "\n".join(lines)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def build_payload(data_dir: Path | None = None) -> dict[str, Any]:
    data_dir = data_dir or (REPO_ROOT / "data")
    timestamp = _utc_now()
    candidates, features_by_date = load_candidates(data_dir)
    ledger_map = load_ledger_map(data_dir)
    prices = build_price_lookup(data_dir)
    annotated = annotate_candidates(
        candidates=candidates,
        features_by_date=features_by_date,
        ledger_map=ledger_map,
        prices=prices,
    )
    readiness_summary = build_readiness_summary(annotated)
    readiness_gate = evaluate_readiness_gate(readiness_summary)
    field_check = _open_position_field_check()
    decision = readiness_gate["decision"]
    status = "observed_only" if readiness_gate["passed"] else "observed_only_data_gap"
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(DOC_LOG),
        _repo_rel(DOC_TICKET),
        _repo_rel(DOC_ARTIFACT),
        _repo_rel(EXPERIMENT_LOG_JSONL),
    ]
    bucket_a_closed = readiness_gate["bucket_a_closed_5d_outcomes"]
    total_usable = readiness_gate["total_usable_candidates"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "measurement_repair",
        "read_only": True,
        "hypothesis": (
            "Expectation drift x residual leadership remains blocked until "
            "PIT estimate-revision joins, residual context, and closed forward "
            "outcomes produce enough Bucket A observations for attribution."
        ),
        "change_summary": (
            "Read-only readiness audit for the existing expectation-residual "
            "leadership attribution experiment."
        ),
        "change_type": "measurement_repair_readiness_audit",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "readiness_audit_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 1,
        "nearby_prior_experiments": ["exp-20260525-017", "exp-20260524-012"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "expectation_residual_coverage_readiness_audit",
        "component": "quant/experiments/exp_20260525_021_expectation_residual_readiness_audit.py",
        "parameters": {
            "positive_expectation_definition": "estimate_revision_usable && eps_estimate_delta_7d > 0",
            "no_expectation_fallback": True,
            "residual_leader_states": sorted(RESIDUAL_LEADER_STATES),
            "forward_horizons": list(FORWARD_HORIZONS),
            "readiness_gate_thresholds": {
                "min_bucket_a_5d_outcomes": MIN_BUCKET_A_5D_OUTCOMES,
                "min_total_usable_candidates": MIN_TOTAL_USABLE_CANDIDATES,
            },
            "alpha_interpretation_guardrails": {
                "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
                "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
            },
            "exact_rerun_command": RERUN_COMMAND,
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            "candidate_artifacts": "data/daily/signals/quant/quant_signals_*.json",
            "estimate_revision_ledgers": "data/non_ohlcv/estimate_revision_ledger_*.jsonl",
            "ohlcv_sources": [
                "data/ohlcv/ohlcv_snapshot_*.json",
                "data/daily/signals/trend/trend_signals_*.json",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "measurement repair for the expectation-residual alpha path: "
                "determine whether the existing read-only attribution has enough "
                "coverage to be interpreted."
            ),
            "2_history_check": (
                "exp-20260525-017 found Bucket A = 0 and total usable 20, so "
                "the alpha result is coverage-blocked rather than accepted or rejected."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Readiness gate: Bucket A closed 5d outcomes >= 8 and total "
                "5d closed candidates >= 30, with all non-ready reasons explained."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260525_021_expectation_residual_readiness_audit.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
            "baseline_artifact": "data/experiments/exp-20260517-009/",
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "note": "This readiness audit is read-only; no before/after core metrics are changed.",
        },
        "gate2": {
            "passed": bool(field_check.get("passed", False)),
            "field_check": field_check,
            "rule_dependencies": [
                "daily quant candidate objects",
                "estimate_revision_ledger rows by as_of_date/ticker",
                "quant features for residual strength",
                "local OHLCV/trend close rows for forward returns",
            ],
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "passed": True,
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "passed": readiness_gate["passed"],
            "note": (
                "Passing this gate only permits rerunning exp-20260525-017 for "
                "read-only interpretation; it does not promote PEAD, ranking, "
                "sizing, or live behavior."
            ),
        },
        "readiness_summary": readiness_summary,
        "readiness_gate": readiness_gate,
        "before_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
            "candidate_objects_total": readiness_summary["candidate_objects_total"],
            "bucket_a_closed_5d_outcomes": bucket_a_closed,
            "total_usable_candidates": total_usable,
            "ready_to_rerun_attribution": readiness_gate["ready_to_rerun_attribution"],
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": 0.0,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": production_impact(),
        "decision_rule": (
            "If readiness_gate.ready_to_rerun_attribution is false, do not "
            "advance to PEAD paper sleeve or ranking-score replacement tests."
        ),
        "rejection_reason": None
        if readiness_gate["passed"]
        else "insufficient expectation-residual readiness coverage",
        "next_evidence_needed": (
            "Keep accumulating PIT estimate-revision ledgers and daily candidate "
            "objects; rerun this audit until Bucket A has >=8 closed 5d outcomes "
            "and total usable candidates >=30."
        ),
        "related_files": related_files,
        "anti_js": "No JavaScript was used.",
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "experiment_id",
        "timestamp",
        "status",
        "hypothesis",
        "change_summary",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "component",
        "parameters",
        "date_range",
        "gate_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "readiness_summary",
        "readiness_gate",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "expected_value_score_delta",
        "llm_metrics",
        "production_impact",
        "decision",
        "decision_rule",
        "rejection_reason",
        "next_evidence_needed",
        "related_files",
        "anti_js",
    )
    return {key: payload[key] for key in keys}


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "measurement_repair",
            "owner": "codex",
            "status": payload["status"],
            "decision": payload["decision"],
            "single_causal_variable": CHANGED_VARIABLE,
            "artifact_file": _repo_rel(OUT_JSON),
            "result_file": _repo_rel(DOC_LOG),
            "updated_at": payload["timestamp"],
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "status": payload["status"],
                    "readiness_gate": payload["readiness_gate"],
                    "output": _repo_rel(OUT_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
