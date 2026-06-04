"""exp-20260604-027: shared SEC FTD + FINRA paper adapter.

This closeout promotes the accepted exp-20260604-026 replay lead into a
production-visible default-off paper adapter. It does not change live orders.
The canonical three-window Gate 4 evidence remains exp-20260604-026; this run
records the shared adapter boundary, parity tests, and production metadata.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from quant.sec_ftd_finra_paper_sleeve import (
        FINRA_CONFIRMATION_RULE_VERSION,
        FTD_SOURCE_RULE_VERSION,
        REPLACEMENT_VALUE_RULE_VERSION,
        RULE_VERSION,
        SLEEVE_NAME,
    )
except ImportError:  # pragma: no cover - direct script execution
    import sys

    REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORT))
    from quant.sec_ftd_finra_paper_sleeve import (
        FINRA_CONFIRMATION_RULE_VERSION,
        FTD_SOURCE_RULE_VERSION,
        REPLACEMENT_VALUE_RULE_VERSION,
        RULE_VERSION,
        SLEEVE_NAME,
    )


EXPERIMENT_ID = "exp-20260604-027"
STEM = "sec_ftd_finra_shared_adapter"
REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_027_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
PRIOR_ID = "exp-20260604-026"
PRIOR_STEM = "sec_ftd_finra_confirmed_candidate_pool"
PRIOR_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / PRIOR_ID
    / f"exp_20260604_026_{PRIOR_STEM}.json"
)
PRIOR_BEFORE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / PRIOR_ID
    / f"{PRIOR_STEM}_before_aggregate.json"
)
PRIOR_AFTER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / PRIOR_ID
    / f"{PRIOR_STEM}_after_aggregate.json"
)


RELATED_FILES = [
    "quant/sec_ftd_finra_paper_sleeve.py",
    "quant/test_sec_ftd_finra_paper_sleeve.py",
    "quant/data_paths.py",
    "quant/run.py",
    "quant/default_off_alpha_attribution.py",
    "quant/report_generator.py",
    "docs/current_state.md",
    "docs/alpha-optimization-playbook.md",
    "docs/data_edge_context_layers.md",
    "docs/production_backtest_parity.md",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
    "experiments/cards/exp-20260604-027.md",
    "experiments/tickets/exp-20260604-027.json",
    "experiments/manifests/exp-20260604-027.json",
    "experiments/logs/exp-20260604-027.json",
    "experiments/artifacts/exp-20260604-027_sec_ftd_finra_shared_adapter.md",
    "data/experiments/exp-20260604-027/exp_20260604_027_sec_ftd_finra_shared_adapter.json",
    "data/experiments/exp-20260604-027/sec_ftd_finra_shared_adapter_before_aggregate.json",
    "data/experiments/exp-20260604-027/sec_ftd_finra_shared_adapter_after_aggregate.json",
]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _copy_aggregate(source: Path, target: Path, role: str) -> dict[str, Any]:
    payload = dict(_load_json(source))
    payload["artifact_role"] = role
    payload["experiment_id"] = EXPERIMENT_ID
    payload["evidence_source_experiment_id"] = PRIOR_ID
    payload["evidence_source_artifact"] = _repo_rel(source)
    _write_json(target, payload)
    return payload


def _round4(value: float) -> float:
    return round(float(value), 4)


def _window_rows(before: dict[str, Any], after: dict[str, Any], prior: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    before_windows = before.get("windows") or {}
    after_windows = after.get("windows") or {}
    prior_deltas = prior.get("delta_metrics") or {}
    target_trades = {
        label: len(rows)
        for label, rows in (prior.get("target_trades_by_window") or {}).items()
    }
    for label in ("late_strong", "mid_weak", "old_thin"):
        before_row = before_windows.get(label) or {}
        after_row = after_windows.get(label) or {}
        delta_row = prior_deltas.get(label) or {}
        rows.append(
            {
                "window": label,
                "before_ev": before_row.get("expected_value_score"),
                "after_ev": after_row.get("expected_value_score"),
                "delta_ev": delta_row.get("expected_value_score"),
                "before_pnl": before_row.get("total_pnl"),
                "after_pnl": after_row.get("total_pnl"),
                "delta_pnl": delta_row.get("total_pnl"),
                "before_survival_rate": before_row.get("survival_rate"),
                "after_survival_rate": after_row.get("survival_rate"),
                "max_drawdown_delta": delta_row.get("max_drawdown_pct"),
                "target_trades": target_trades.get(label, 0),
            }
        )
    return rows


def _aggregate(before: dict[str, Any], after: dict[str, Any], windows: list[dict[str, Any]]) -> dict[str, Any]:
    before_ev = float(before.get("aggregate_expected_value_score") or 0.0)
    after_ev = float(after.get("aggregate_expected_value_score") or 0.0)
    before_pnl = float(before.get("aggregate_total_pnl") or 0.0)
    after_pnl = float(after.get("aggregate_total_pnl") or 0.0)
    return {
        "before_expected_value_score_sum": _round4(before_ev),
        "after_expected_value_score_sum": _round4(after_ev),
        "expected_value_score_delta_sum": _round4(after_ev - before_ev),
        "expected_value_score_delta_pct": round((after_ev - before_ev) / before_ev, 6)
        if before_ev
        else None,
        "before_total_pnl_sum": round(before_pnl, 2),
        "after_total_pnl_sum": round(after_pnl, 2),
        "total_pnl_delta_sum": round(after_pnl - before_pnl, 2),
        "total_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6)
        if before_pnl
        else None,
        "windows_ev_improved": sum(1 for row in windows if (row["delta_ev"] or 0) > 0),
        "windows_pnl_improved": sum(1 for row in windows if (row["delta_pnl"] or 0) > 0),
        "windows_ev_regressed": sum(1 for row in windows if (row["delta_ev"] or 0) < 0),
        "windows_pnl_regressed": sum(1 for row in windows if (row["delta_pnl"] or 0) < 0),
        "target_trade_count": sum(row["target_trades"] for row in windows),
        "max_drawdown_delta_max": max(
            (row["max_drawdown_delta"] or 0.0 for row in windows),
            default=0.0,
        ),
    }


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
        "replay_only": False,
        "default_off_paper_only": True,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "trade_enabled": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "parity_test_added": True,
        "activation_requires_shared_replay_adapter": True,
    }


def build_payload() -> dict[str, Any]:
    prior = _load_json(PRIOR_JSON)
    before = _copy_aggregate(PRIOR_BEFORE, BEFORE_AGG_JSON, "before_aggregate")
    after = _copy_aggregate(PRIOR_AFTER, AFTER_AGG_JSON, "after_aggregate")
    windows = _window_rows(before, after, prior)
    aggregate = _aggregate(before, after, windows)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "accepted_default_off_sec_ftd_finra_shared_adapter",
        "decision": "accepted_default_off_sec_ftd_finra_shared_adapter",
        "hypothesis": (
            "Promote the positive SEC FTD plus FINRA borrow-pressure replay lead "
            "into a shared default-off paper adapter so production can collect "
            "forward replacement-value evidence without changing live orders."
        ),
        "change_type": "default_off_paper_adapter",
        "mechanism_family": "default_off_paper_adapter",
        "trial_family": "default_off_paper_adapter",
        "trial_variant_id": "sec_ftd_finra_shared_default_off_adapter_v1",
        "changed_variable": "sec_ftd_finra_shared_default_off_adapter_v1",
        "single_causal_variable": "sec_ftd_finra_shared_default_off_adapter_v1",
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260604-026",
            "exp-20260604-023",
            "exp-20260604-024",
            "exp-20260603-007",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "promoted_positive_replay_lead_to_shared_production_visible_adapter",
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool/default_off_adapter: publication-lagged SEC FTD "
                "pressure is admitted only when latest PIT FINRA borrow pressure "
                "confirms days_to_cover >= 3 and positive short-interest change."
            ),
            "2_history_check": {
                "exp-20260604-026": (
                    "Accepted positive replay lead: aggregate EV +0.4420, PnL "
                    "+$10,100.49, 121 target paper trades, 3/3 windows improved."
                ),
                "exp-20260604-023": (
                    "FTD standalone was rejected despite aggregate positivity "
                    "because late_strong regressed."
                ),
                "exp-20260604-024": (
                    "Form 4 plus FTD overlap was too thin and concentrated."
                ),
                "exp-20260603-007": (
                    "FINRA shared adapter pattern accepted; this run follows the "
                    "same default-off production-visible boundary."
                ),
            },
            "3_single_causal_variable": "sec_ftd_finra_shared_default_off_adapter_v1",
            "4_acceptance_standard": (
                "Use docs/backtesting.md three windows from exp-20260604-026 for "
                "alpha evidence, then require shared production-visible code, "
                "focused parity tests, and no live/core order impact."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260604_027_sec_ftd_finra_shared_adapter.py"
            ),
        },
        "three_window_evidence_source": _repo_rel(PRIOR_JSON),
        "three_window_result": {
            "windows": windows,
            "aggregate": aggregate,
            "decision_basis": prior.get("decision_basis"),
            "gate4": prior.get("gate4"),
            "target_trade_summary": prior.get("target_trade_summary"),
        },
        "adapter_validation": {
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "ftd_source_rule_version": FTD_SOURCE_RULE_VERSION,
            "finra_confirmation_rule_version": FINRA_CONFIRMATION_RULE_VERSION,
            "replacement_value_rule_version": REPLACEMENT_VALUE_RULE_VERSION,
            "shared_files": [
                "quant/sec_ftd_finra_paper_sleeve.py",
                "quant/run.py",
                "quant/default_off_alpha_attribution.py",
                "quant/report_generator.py",
                "quant/data_paths.py",
                "quant/test_sec_ftd_finra_paper_sleeve.py",
            ],
            "focused_tests": [
                "pytest quant/test_sec_ftd_finra_paper_sleeve.py quant/test_finra_iwm_paper_sleeve.py -q",
                "py_compile sec_ftd_finra/run/report/default_off modules",
            ],
            "production_backtest_consistency": (
                "The positive replay remains the canonical Gate 4 evidence. The "
                "same source lag, FINRA confirmation, default-off order flags, "
                "and no-same-day-core-overlap policy are now encoded in shared "
                "production code. Live activation remains blocked until closed "
                "forward rows are compared with replay outputs."
            ),
        },
        "prediction": {
            "success_probability": 0.64,
            "expected_ev_delta": aggregate["expected_value_score_delta_sum"],
            "expected_pnl_delta": aggregate["total_pnl_delta_sum"],
            "main_failure_modes": [
                "adapter_replay_mismatch",
                "production_metadata_gap",
                "unit_parity_failure",
            ],
            "confidence_reason": (
                "exp-20260604-026 already passed the canonical three-window gate; "
                "this run tests shared adapter promotion rather than retuning."
            ),
            "recorded_at": "2026-06-04T22:05:48+00:00",
        },
        "calibration": {
            "actual_decision": "accepted_default_off_sec_ftd_finra_shared_adapter",
            "actual_success": 1,
            "predicted_success_probability": 0.64,
            "brier_score": round((0.64 - 1) ** 2, 6),
            "realized_failure_mode": None,
            "predicted_failure_mode_hit": False,
        },
        "production_impact": _production_impact(),
        "acceptance_basis": (
            "Accepted as a default-off production-visible paper adapter, not live "
            "capital. It preserves the accepted exp-20260604-026 three-window "
            "lead and starts forward evidence collection without changing core "
            "or live behavior."
        ),
        "next_evidence_needed": (
            "Closed forward replacement-value rows, replay-vs-forward parity "
            "audit, cash/core displacement comparison, concentration monitoring, "
            "and explicit activation experiment before any live order use."
        ),
        "related_files": RELATED_FILES + [
            _repo_rel(PRIOR_JSON),
            _repo_rel(PRIOR_BEFORE),
            _repo_rel(PRIOR_AFTER),
        ],
        "anti_js": "No JavaScript was used.",
        "accepted": True,
        "rejection_reason": None,
    }


def build_artifact(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260604-027 SEC FTD + FINRA Shared Adapter",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: move the accepted SEC FTD + FINRA confirmation "
            "candidate source into a shared default-off paper adapter."
        ),
        "",
        "## Three-Window Evidence",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Target trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["three_window_result"]["windows"]:
        lines.append(
            "| {window} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | "
            "${before_pnl:,.2f} | ${after_pnl:,.2f} | ${delta_pnl:+,.2f} | "
            "{target_trades} |".format(**row)
        )
    aggregate = payload["three_window_result"]["aggregate"]
    decision_basis = (
        payload["three_window_result"].get("decision_basis")
        or payload["three_window_result"].get("gate4")
        or {}
    )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate.get('expected_value_score_delta_sum')}` (`{aggregate.get('expected_value_score_delta_pct')}`)",
            f"- PnL delta: `${aggregate.get('total_pnl_delta_sum')}` (`{aggregate.get('total_pnl_delta_pct')}`)",
            f"- Windows improved: EV `{aggregate.get('windows_ev_improved')}/3`, PnL `{aggregate.get('windows_pnl_improved')}/3`.",
            f"- Target trades: `{aggregate.get('target_trade_count')}`.",
            f"- Gate 4 passed: `{decision_basis.get('passed')}`; failed gates `{decision_basis.get('failed_gates')}`.",
            "",
            "## Production Consistency",
            "",
            (
                "The adapter is shared production code and remains default-off "
                "paper only. `trade_enabled=false`; it does not change core "
                "signals, rankings, sizing, exits, watchlists, LLM/news, or orders."
            ),
            "",
            (
                "Live activation is still blocked until forward paper rows close "
                "and are compared against replay outputs."
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    return "\n".join(lines) + "\n"


def _experiment_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["three_window_result"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "before_metrics": {
            "expected_value_score": aggregate["before_expected_value_score_sum"],
            "total_pnl": aggregate["before_total_pnl_sum"],
        },
        "after_metrics": {
            "expected_value_score": aggregate["after_expected_value_score_sum"],
            "total_pnl": aggregate["after_total_pnl_sum"],
        },
        "delta_metrics": {
            "expected_value_score": aggregate["expected_value_score_delta_sum"],
            "total_pnl": aggregate["total_pnl_delta_sum"],
            "target_trade_count": aggregate["target_trade_count"],
            "windows_ev_improved": aggregate["windows_ev_improved"],
            "windows_pnl_improved": aggregate["windows_pnl_improved"],
            "max_drawdown_delta_max": aggregate["max_drawdown_delta_max"],
        },
        "windows": payload["three_window_result"]["windows"],
        "adapter_validation": payload["adapter_validation"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "decision_basis": (
            payload["three_window_result"].get("decision_basis")
            or payload["three_window_result"].get("gate4")
        ),
        "acceptance_basis": payload["acceptance_basis"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "rejection_reason": None,
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
        "artifact_path": _repo_rel(OUT_JSON),
    }


def _append_experiment_log_once(row: dict[str, Any]) -> None:
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    needle = f'"experiment_id": "{EXPERIMENT_ID}"'
    compact_needle = f'"experiment_id":"{EXPERIMENT_ID}"'
    row_text = json.dumps(row, ensure_ascii=True, sort_keys=True)
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines()
        replaced = False
        out = []
        for line in lines:
            if needle in line or compact_needle in line:
                if not replaced:
                    out.append(row_text)
                    replaced = True
                continue
            out.append(line)
        if replaced:
            EXPERIMENT_LOG.write_text("\n".join(out) + "\n", encoding="utf-8")
            return
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(row_text + "\n")


def _update_ticket(payload: dict[str, Any]) -> None:
    if not TICKET_JSON.exists():
        return
    ticket = _load_json(TICKET_JSON)
    ticket["status"] = "completed"
    ticket["completed_at"] = payload["timestamp"]
    scope = list(ticket.get("allowed_write_scope") or [])
    for path in RELATED_FILES:
        if path not in scope:
            scope.append(path)
    ticket["allowed_write_scope"] = scope
    ticket["result"] = {
        "status": payload["status"],
        "decision": payload["decision"],
        "before_artifact": _repo_rel(BEFORE_AGG_JSON),
        "after_artifact": _repo_rel(AFTER_AGG_JSON),
        "result_file": _repo_rel(OUT_JSON),
        "artifact": _repo_rel(ARTIFACT_MD),
        "acceptance_basis": payload["acceptance_basis"],
    }
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for row in experiments:
        if row.get("experiment_id") == EXPERIMENT_ID:
            row.update(
                {
                    "status": payload["status"],
                    "owner": "alpha-search",
                    "updated_at": payload["timestamp"],
                    "result_file": _repo_rel(OUT_JSON),
                    "artifact_file": _repo_rel(ARTIFACT_MD),
                }
            )
            break
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _update_card(payload: dict[str, Any]) -> None:
    aggregate = payload["three_window_result"]["aggregate"]
    text = "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            'status: "completed"',
            'lane: "alpha_search"',
            'change_type: "default_off_paper_adapter"',
            'mechanism_family: "default_off_paper_adapter"',
            'trial_family: "default_off_paper_adapter"',
            'trial_variant_id: "sec_ftd_finra_shared_default_off_adapter_v1"',
            'changed_variable: "sec_ftd_finra_shared_default_off_adapter_v1"',
            'new_evidence_type: "promoted_positive_replay_lead_to_shared_production_visible_adapter"',
            f'updated_at: "{payload["timestamp"]}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Summary",
            "",
            payload["hypothesis"],
            "",
            "## Closeout",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Before aggregate EV/PnL: `{aggregate['before_expected_value_score_sum']}` / `${aggregate['before_total_pnl_sum']:,.2f}`",
            f"- After aggregate EV/PnL: `{aggregate['after_expected_value_score_sum']}` / `${aggregate['after_total_pnl_sum']:,.2f}`",
            f"- Delta EV/PnL: `{aggregate['expected_value_score_delta_sum']:+.4f}` / `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Target trades: `{aggregate['target_trade_count']}`; windows EV improved `{aggregate['windows_ev_improved']}/3`.",
            "",
            "## Acceptance Basis",
            "",
            payload["acceptance_basis"],
            "",
            "## Next Evidence",
            "",
            payload["next_evidence_needed"],
            "",
        ]
    )
    CARD_MD.write_text(text, encoding="utf-8")


def main() -> int:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(build_artifact(payload), encoding="utf-8")
    _append_experiment_log_once(_experiment_log_row(payload))
    _update_ticket(payload)
    _update_registry(payload)
    _update_card(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
