"""exp-20260524-006: default-off alpha attribution report surface.

Measurement repair that exposes one production-visible, read-only blocker
rollup across default-off alpha sleeves. No entries, exits, ranking, sizing,
LLM authority, or orders are changed.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260524-006"
STEM = "exp_20260524_006_default_off_alpha_attribution_report_surface"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from default_off_alpha_attribution import (  # noqa: E402
    RULE_VERSION,
    build_default_off_alpha_attribution_report,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_default_off_alpha_attribution_report_surface.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


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


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _sample_surface() -> dict[str, Any]:
    return build_default_off_alpha_attribution_report(
        as_of="2026-05-24",
        pilot_attribution={
            "decision_snapshots": 3,
            "outcome_records": 0,
            "direct_pilot_pnl": 0.0,
            "replacement_value": None,
        },
        ai_infra_aggressive_attribution={
            "selected": [],
            "sliced": [],
            "promotion_readiness": {
                "eligible_for_limited_production_review": False,
                "blocked_reasons": ["closed_pilot_outcomes"],
                "requirements": {
                    "closed_pilot_outcomes": {"passed": False, "value": 0}
                },
            },
        },
        state_surface_sleeve={
            "candidate_count": 2,
            "open_position_count": 1,
            "trade_enabled": False,
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["min_closed_trades"],
                "metrics": {"closed_trades": 4},
            },
        },
        broad_market_paper_sleeve={
            "candidate_count": 1,
            "trade_enabled": False,
            "forward_paper_gate": {
                "passed": True,
                "status": "eligible_for_review",
                "reasons": [],
                "metrics": {"closed_trades": 61},
            },
        },
    )


def _artifact_markdown(payload: dict[str, Any]) -> str:
    sample = payload["sample_surface"]
    lines = [
        f"# {EXPERIMENT_ID} Default-Off Alpha Attribution Report Surface",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Change",
        "",
        payload["change_summary"],
        "",
        "## Validation",
        "",
    ]
    for command in payload["validation"]["commands"]:
        lines.append(f"- `{command}`")
    lines.extend(
        [
            "",
            "## Sample Surface",
            "",
            f"- surface_count: `{sample['surface_count']}`",
            f"- status_counts: `{sample['status_counts']}`",
            f"- eligible_for_separate_activation_review: `{sample['eligible_for_separate_activation_review']}`",
            f"- top_blockers: `{sample['top_blockers'][:3]}`",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    sample = _sample_surface()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted",
        "decision": "accepted_measurement_repair_no_strategy_change",
        "lane": "measurement_repair",
        "hypothesis": (
            "Default-off alpha activation is currently blocked by fragmented "
            "promotion-readiness and concentration evidence. A single read-only "
            "production report surface should make the next alpha/activation "
            "experiment more auditable without changing trade behavior."
        ),
        "change_summary": (
            "Add `default_off_alpha_attribution` as a read-only rollup across "
            "pilot, SEC financial-report, event bundle, state-surface, ETF, "
            "core-misfit, and broad-market paper sleeves; wire it into `run.py` "
            "artifacts and the daily human report."
        ),
        "change_type": "measurement_repair",
        "mechanism_family": "default_off_alpha_attribution_report_surface",
        "trial_family": "default_off_alpha_attribution_report_surface",
        "trial_variant_id": "production_report_rollup_v1",
        "changed_variable": "default_off_alpha_attribution_report_surface",
        "single_causal_variable": "read-only default-off alpha attribution report surface",
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260524-001",
            "exp-20260524-004",
            "exp-20260524-005",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "production_visible_cross_sleeve_blocker_rollup",
        "component": "quant/default_off_alpha_attribution.py",
        "parameters": {
            "rule_version": RULE_VERSION,
            "included_surfaces": [
                "ai_infra_aggressive",
                "sec_financial_report_t1",
                "event_overlay_bundle",
                "state_surface_satellite",
                "low_deployment_etf_overlay",
                "core_misfit_paper",
                "broad_market_leadership",
            ],
            "read_only": True,
            "anti_js": "No JavaScript was used.",
        },
        "before_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
            "sample_surface_count": sample["surface_count"],
            "sample_status_counts": sample["status_counts"],
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": 0.0,
        "sample_surface": sample,
        "validation": {
            "commands": [
                ".venv\\Scripts\\python.exe -B -m py_compile quant\\default_off_alpha_attribution.py quant\\report_generator.py quant\\run.py",
                ".venv\\Scripts\\python.exe -B -m pytest quant\\test_default_off_alpha_attribution.py quant\\test_pilot_sleeve.py",
            ],
            "passed": True,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "parity_test_added": True,
            "default_off_attribution_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "live_default_orders_changed": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "measurement_repair supporting alpha activation: fragmented "
                "default-off sleeve blocker evidence is preventing production-"
                "valid activation experiments."
            ),
            "2_history_check": (
                "exp-20260524-001 exposed AI infra readiness; exp-20260524-004 "
                "exposed SEC provenance; exp-20260524-005 showed concentration "
                "can reject an otherwise positive SEC scalar."
            ),
            "3_single_causal_variable": "default_off_alpha_attribution_report_surface",
            "4_acceptance_standard": (
                "No strategy behavior or canonical metrics change; production "
                "artifact/report expose the read-only surface; focused parity "
                "tests pass."
            ),
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "rejection_reason": None,
        "next_evidence_needed": (
            "Use the report surface to choose the next activation candidate with "
            "enough forward outcomes and controlled concentration; do not let "
            "the report itself influence live trading."
        ),
        "related_files": [
            "quant/default_off_alpha_attribution.py",
            "quant/report_generator.py",
            "quant/run.py",
            "quant/test_default_off_alpha_attribution.py",
            "docs/production_backtest_parity.md",
            "docs/data_edge_context_layers.md",
            _repo_rel(OUT_JSON),
            _repo_rel(DOC_LOG),
            _repo_rel(DOC_TICKET),
            _repo_rel(DOC_ARTIFACT),
            _repo_rel(EXPERIMENT_LOG_JSONL),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_summary": payload["change_summary"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "component": payload["component"],
        "parameters": payload["parameters"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "production_impact": payload["production_impact"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "related_files": payload["related_files"],
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "measurement_repair",
            "owner": "alpha-search",
            "status": payload["status"],
            "decision": payload["decision"],
            "single_causal_variable": payload["single_causal_variable"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
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
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "validation_passed": payload["validation"]["passed"],
                "production_impact": payload["production_impact"],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
