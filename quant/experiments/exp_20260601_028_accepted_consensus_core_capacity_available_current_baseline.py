"""exp-20260601-028: current-baseline consensus core-capacity gate.

Lane: alpha_search.
Single causal variable:
    accepted_free_data_consensus_core_capacity_available_gate_v2_current_baseline.

This retests the positive exp-20260601-018 capacity discriminator against the
current PIT-DTE canonical three-window baseline, then records whether the same
rule is present in the shared default-off production adapter. No JavaScript is
used.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import (  # noqa: E402
    exp_20260601_018_accepted_consensus_core_capacity_available as prior,
)


EXPERIMENT_ID = "exp-20260601-028"
STEM = "accepted_consensus_core_capacity_available_current_baseline"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_capacity_gate"
CHANGED_VARIABLE = (
    "accepted_free_data_consensus_core_capacity_available_gate_v2_current_baseline"
)
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260601_028_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"exp_20260601_028_{STEM}_before.json"
AFTER_JSON = OUT_DIR / f"exp_20260601_028_{STEM}_after.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"

CURRENT_DOCS_BASELINE = {
    "late_strong": {"expected_value_score": 4.1082, "total_pnl": 100_203.06},
    "mid_weak": {"expected_value_score": 2.1405, "total_pnl": 78_119.38},
    "old_thin": {"expected_value_score": 0.1109, "total_pnl": 14_216.17},
}

PRODUCTION_IMPACT = {
    "replay_only": False,
    "default_off_paper_only": True,
    "shared_policy_changed": True,
    "run_adapter_changed": True,
    "backtester_adapter_changed": False,
    "parity_test_added": True,
    "trade_enabled": False,
    "alters_orders": False,
    "production_orders_changed": False,
    "production_signal_path_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
}

ADAPTER_FILES = [
    "quant/free_data_cross_source_consensus_paper_sleeve.py",
    "quant/run.py",
    "quant/report_generator.py",
    "quant/test_free_data_cross_source_consensus_paper_sleeve.py",
    "docs/production_backtest_parity.md",
    "docs/current_state.md",
    "docs/alpha-optimization-playbook.md",
    "docs/data_edge_context_layers.md",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(_safe(record), sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                item = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if item.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _configure_prior_module() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.RULE_VERSION = RULE_VERSION
    prior.DOCS_ACCEPTED_BASELINE = CURRENT_DOCS_BASELINE
    prior.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.BEFORE_JSON = BEFORE_JSON
    prior.AFTER_JSON = AFTER_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG


def _baseline_check(core_metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {}
    for label, expected in CURRENT_DOCS_BASELINE.items():
        actual = core_metrics_by_window.get(label) or {}
        ev_delta = float(actual.get("expected_value_score") or 0.0) - expected[
            "expected_value_score"
        ]
        pnl_delta = float(actual.get("total_pnl") or 0.0) - expected["total_pnl"]
        rows[label] = {
            "docs_expected_value_score": expected["expected_value_score"],
            "current_expected_value_score": actual.get("expected_value_score"),
            "expected_value_score_delta": round(ev_delta, 6),
            "docs_total_pnl": expected["total_pnl"],
            "current_total_pnl": actual.get("total_pnl"),
            "total_pnl_delta": round(pnl_delta, 2),
            "matches_docs_baseline": abs(ev_delta) <= 0.01 and abs(pnl_delta) <= 100.0,
        }
    return {
        "docs_source": "docs/backtesting.md accepted exp-20260601-025 PIT-DTE metrics",
        "current_source": "current replay in the same docs/backtesting.md windows",
        "matches_all_windows": all(row["matches_docs_baseline"] for row in rows.values()),
        "rows": rows,
    }


def _shared_adapter_check() -> dict[str, Any]:
    try:
        from quant import free_data_cross_source_consensus_paper_sleeve as adapter
    except ImportError as exc:
        return {"passed": False, "reason": f"adapter_import_failed: {exc}"}
    cfg = getattr(adapter, "DEFAULT_CONFIG", {})
    return {
        "passed": bool(
            getattr(adapter, "CORE_CAPACITY_RULE_VERSION", None)
            == "accepted_free_data_consensus_core_capacity_available_gate_v1"
            and cfg.get("require_core_capacity_available") is True
            and cfg.get("trade_enabled") is False
        ),
        "core_capacity_rule_version": getattr(adapter, "CORE_CAPACITY_RULE_VERSION", None),
        "require_core_capacity_available": cfg.get("require_core_capacity_available"),
        "trade_enabled": cfg.get("trade_enabled"),
        "shared_adapter_file": "quant/free_data_cross_source_consensus_paper_sleeve.py",
    }


def _judge(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    baseline_check: dict[str, Any],
    shared_adapter: dict[str, Any],
) -> dict[str, Any]:
    base_gate = prior._judge(aggregate, results, target_summary, baseline_check)
    gates = dict(base_gate["gates"])
    gates["shared_default_off_adapter_present"] = bool(shared_adapter.get("passed"))
    failed_gates = [key for key, value in gates.items() if not value]
    passed = not failed_gates
    if passed:
        decision = "accepted_default_off_consensus_core_capacity_available_adapter"
        rationale = (
            "The current PIT-DTE three-window replay improved aggregate EV/PnL and "
            "all windows, baseline matched docs/backtesting.md, and the same "
            "core-capacity gate now lives in the shared default-off adapter with "
            "trade_enabled=false."
        )
    elif base_gate.get("alpha_checks_passed") and baseline_check.get("matches_all_windows"):
        decision = "positive_replay_lead_not_promoted_missing_shared_adapter"
        rationale = (
            "The replay passed alpha and baseline checks, but the shared default-off "
            "adapter did not expose the same capacity gate."
        )
    else:
        decision = "rejected_consensus_core_capacity_available_current_baseline"
        rationale = (
            "One or more three-window Gate 4 alpha, baseline, risk, sample, or "
            "concentration checks failed."
        )
    return {
        **base_gate,
        "passed": passed,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed_gates,
        "shared_adapter": shared_adapter,
        "requires_parity_before_promotion": False,
    }


def _prediction() -> dict[str, Any]:
    if TICKET_JSON.exists():
        ticket = _load_json(TICKET_JSON)
        if isinstance(ticket.get("prediction"), dict):
            return ticket["prediction"]
    return {
        "success_probability": 0.48,
        "expected_ev_delta": 1.1099,
        "expected_pnl_delta": 22_063.58,
        "main_failure_modes": [
            "window_regression",
            "capacity_not_distinct",
            "concentration_failed",
            "shared_adapter_parity_gap",
        ],
        "confidence_reason": "Fallback copied from reservation intent.",
        "recorded_at": _utc_now(),
    }


def _calibration(prediction: dict[str, Any], gate4: dict[str, Any], aggregate: dict[str, Any]) -> dict[str, Any]:
    actual_success = 1 if gate4["passed"] else 0
    probability = float(prediction.get("success_probability") or 0.0)
    realized = gate4["failed_gates"]
    modes = prediction.get("main_failure_modes") or []
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": probability,
        "brier_score": round((probability - actual_success) ** 2, 6),
        "actual_ev_delta": aggregate["comparison"]["expected_value_score_delta"],
        "actual_pnl_delta": aggregate["comparison"]["strategy_total_pnl_delta"],
        "predicted_failure_modes": modes,
        "realized_failure_mode": realized,
        "predicted_failure_mode_hit": any(
            "window" in mode
            and (
                "all_windows_expected_value_improved" in realized
                or "all_windows_pnl_improved" in realized
            )
            or "capacity" in mode and "distinct_from_no_core_gate" in realized
            or "concentration" in mode and "concentration_guard_passed" in realized
            or "shared_adapter" in mode and "shared_default_off_adapter_present" in realized
            for mode in modes
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": payload["gate4"]["decision"],
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": (
            "Promoted the accepted free-data cross-source consensus paper queue's "
            "core-capacity-available discriminator into the shared default-off adapter."
        ),
        "change_type": "default_off_paper_capacity_gate",
        "mechanism_family": "default_off_paper_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260601-015",
            "exp-20260601-018",
            "exp-20260601-001",
            "exp-20260531-030",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "current_pit_dte_baseline_retest_with_shared_adapter",
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "parameters": payload["rule"],
        "before_metrics": payload["aggregate"]["before"],
        "after_metrics": payload["aggregate"]["after"],
        "delta_metrics": {
            **comparison,
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "extra_capacity_target_trade_count": payload["gate4"][
                "extra_capacity_target_trade_count"
            ],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["capacity_target_trade_count"],
                "extra_capacity_target_trade_count": row["extra_capacity_target_trade_count"],
            }
            for row in payload["results"]
        ],
        "production_impact": PRODUCTION_IMPACT,
        "decision_basis": payload["gate4"],
        "rejection_reason": "; ".join(payload["gate4"]["failed_gates"]) or None,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXPERIMENT_ID} consensus core-capacity current baseline",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: `{comp['expected_value_score_delta']:+.4f}`",
        f"- Aggregate PnL delta: `${comp['strategy_total_pnl_delta']:+,.2f}`",
        f"- Target trades: `{payload['target_summary']['target_trade_count']}`",
        f"- Extra target trades beyond no-core gate: `{payload['gate4']['extra_capacity_target_trade_count']}`",
        f"- Max positive ticker share: `{payload['target_summary']['max_single_positive_share']}`",
        f"- Positive PnL HHI: `{payload['target_summary']['positive_pnl_hhi']}`",
        f"- Baseline matches docs: `{payload['baseline_check']['matches_all_windows']}`",
        f"- Shared adapter present: `{payload['shared_adapter']['passed']}`",
        "",
        "## Three-Window Evidence",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | capacity trades | no-core trades | extra trades | pass candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        lines.append(
            f"| {row['label']} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['comparison']['expected_value_score_delta']:+.4f} | "
            f"${row['comparison']['strategy_total_pnl_delta']:+,.2f} | "
            f"{row['capacity_target_trade_count']} | {row['no_core_target_trade_count']} | "
            f"{row['extra_capacity_target_trade_count']} | {row['capacity_pass_candidate_count']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            payload["gate4"]["rationale"],
            "",
            "No production orders, core ranking/sizing/exits, LLM/news inputs, or "
            "watchlists changed. The shared adapter remains default-off paper only.",
            "",
        ]
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_ticket_and_registry(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": "accepted" if payload["gate4"]["passed"] else "observed_only",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "aggregate_expected_value_delta": payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ],
                "aggregate_strategy_total_pnl_delta": payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)

    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if isinstance(experiments, list):
        for item in experiments:
            if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
                item["status"] = ticket["status"]
                item["decision"] = payload["gate4"]["decision"]
                item["completed_at"] = payload["completed_at"]
                item["updated_at"] = payload["completed_at"]
                item["artifact"] = _repo_rel(OUT_JSON)
                item["log"] = _repo_rel(LOG_JSON)
                item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ]
                item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ]
                break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def run() -> dict[str, Any]:
    _configure_prior_module()
    gate2 = prior.source.base._audit_open_positions()
    if not gate2.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2}")

    results, core_metrics_by_window, target_trades_by_window = prior._run_windows()
    aggregate = prior._aggregate(results)
    target_summary = prior._target_summary(target_trades_by_window)
    baseline_check = _baseline_check(core_metrics_by_window)
    shared_adapter = _shared_adapter_check()
    gate4 = _judge(aggregate, results, target_summary, baseline_check, shared_adapter)
    prediction = _prediction()
    calibration = _calibration(prediction, gate4, aggregate)
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "preflight": {
            "alpha_hypothesis": (
                "Accepted free-data consensus candidates should have cleaner replacement "
                "value when admitted only on dates where the core replay still leaves "
                "unused position capacity after signal-date close."
            ),
            "category": "candidate_pool / capital_allocation_capacity",
            "playbook_alignment": (
                "Revisits the prior positive consensus capacity lead only because the "
                "obsolete baseline mismatch is now resolved by the PIT-DTE baseline; "
                "does not retune source count, source set, cooldown, hold, or notional."
            ),
            "history_check": {
                "exp-20260531-030": "accepted free-data consensus replay lead",
                "exp-20260601-001": "shared observe-only free-data consensus adapter",
                "exp-20260601-015": "positive no-core capacity gate, obsolete baseline blocker",
                "exp-20260601-018": "positive core-capacity gate, obsolete baseline blocker",
                "exp-20260601-025": "current canonical PIT-DTE baseline",
            },
            "single_causal_variable": CHANGED_VARIABLE,
            "acceptance_standard": (
                "docs/backtesting.md three-window before/after comparison. Retain only "
                "if aggregate EV/PnL and all windows improve, risk/sample/concentration "
                "guards pass, baseline matches current docs, and the shared adapter "
                "remains default-off with trade_enabled=false."
            ),
            "reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260601_028_accepted_consensus_core_capacity_available_current_baseline.py"
            ),
        },
        "prediction": prediction,
        "calibration": calibration,
        "rule": {
            "rule_version": RULE_VERSION,
            "shared_adapter_rule_version": "accepted_free_data_consensus_core_capacity_available_gate_v1",
            "source_adapter_experiment_id": "exp-20260601-001",
            "source_replay_experiment_id": "exp-20260531-030",
            "capacity_gate": "admit only if active core positions after signal-date close are below MAX_POSITIONS",
            "max_core_positions": prior.MAX_POSITIONS,
            "base_notional_usd": prior.source.BASE_NOTIONAL_USD,
            "hold_days": prior.source.HOLD_DAYS,
            "max_paper_trades_per_day": prior.source.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": prior.source.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "shared_adapter": shared_adapter,
        "gate1": {
            "source": "docs/backtesting.md canonical PIT-DTE three-window replay",
            "core_baseline_metrics": core_metrics_by_window,
            "baseline_check": baseline_check,
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2,
            "runtime_fields": [
                "accepted free-data source paper rows",
                "baseline core trade entry_date and exit_date",
                "MAX_POSITIONS from quant/constants.py",
                "operator_inputs/open_positions.json core active position count in production",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
        },
        "gate3": {
            "passed": min(float(row["after"].get("survival_rate") or 0.0) for row in results) >= 0.05,
            "note": "No core/live filter was added; this is a default-off paper capacity discriminator.",
            "survival_by_window": {
                row["label"]: row["after"].get("survival_rate") for row in results
            },
        },
        "gate4": gate4,
        "aggregate": aggregate,
        "baseline_check": baseline_check,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "next_retry_requires": [
            "closed forward replacement-value rows before any trade-enabled activation",
            "do not retune source-count, source-set, cooldown, hold, or notional on frozen windows",
            "new PIT replacement-value surface before any nearby consensus capacity retry",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            *ADAPTER_FILES,
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, aggregate["before"])
    _write_json(AFTER_JSON, aggregate["after"])
    _write_json(LOG_JSON, _experiment_log_record(payload))
    _write_card(payload)
    _update_ticket_and_registry(payload)
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_record(payload))
    return payload


def main() -> None:
    payload = run()
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "gate4": payload["gate4"],
                "target_summary": {
                    key: payload["target_summary"][key]
                    for key in (
                        "target_trade_count",
                        "target_trade_pnl_usd",
                        "pnl_by_window",
                        "max_single_positive_share",
                        "positive_pnl_hhi",
                    )
                },
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
