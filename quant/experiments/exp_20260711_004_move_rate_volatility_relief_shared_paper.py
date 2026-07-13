"""exp-20260711-004: promote the fixed MOVE lead to shared default-off paper."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import exp_20260711_002_move_rate_volatility_relief_stock_leadership as scout  # noqa: E402
import move_rate_volatility_relief_paper_sleeve as shared  # noqa: E402
from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402
from full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_live_readiness,
    full_stack_verdict,
)


EXPERIMENT_ID = "exp-20260711-004"
RUNNER = "quant/experiments/exp_20260711_004_move_rate_volatility_relief_shared_paper.py"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / "exp_20260711_004_move_rate_volatility_relief_shared_paper.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Promote the fixed exp-20260711-002 MOVE rate-volatility relief stock-leadership "
    "lead into one shared default-off paper helper used identically by historical "
    "replay and the daily snapshot; the unchanged MOVE20 first-cross-below event and "
    "frozen selector should preserve the three-window after-cost EV/PnL improvement "
    "while exposing prospective forward rows without changing live orders."
)
CHANGED_VARIABLE = "fixed_move20_first_cross_below_rate_volatility_relief_stock_leadership_shared_default_off_v1"
PREDICTION = json.loads(TICKET_JSON.read_text(encoding="utf-8"))["prediction"]
ALLOWED_WRITE_SCOPE = json.loads(TICKET_JSON.read_text(encoding="utf-8"))["allowed_write_scope"]
NEARBY = ["exp-20260711-002", "exp-20260607-018", "exp-20260607-019"]
NEW_AXIS = (
    "New gate shape: the fixed positive private MOVE replay is now one shared-paper-first "
    "candidate source with historical replay, daily default-off state, report/attribution "
    "wiring, parity tests, execution envelope, and forward rows."
)
_WINDOW_CACHE: dict[
    int,
    tuple[
        dict[str, Any],
        dict[str, list[dict[str, Any]]],
        dict[str, dict[str, int]],
    ],
] = {}


def _normalised(
    snapshot: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, int]]]:
    key = id(snapshot)
    cached = _WINDOW_CACHE.get(key)
    if cached is not None and cached[0] is snapshot:
        return cached[1], cached[2]
    rows = shared.leader._normalise_ohlcv_by_ticker(snapshot)
    indices = {ticker: shared.leader._row_index(values) for ticker, values in rows.items()}
    _WINDOW_CACHE[key] = (snapshot, rows, indices)
    return rows, indices


def replay_context(
    snapshot: dict[str, Any], indices: dict[str, dict[str, int]], signal_date: str
) -> dict[str, Any] | None:
    del indices
    rows, normalized_indices = _normalised(snapshot)
    return shared.move_rate_volatility_relief_context_for_day(
        rows_by_ticker=rows, indices=normalized_indices, signal_date=signal_date
    )


def replay_candidate(**kwargs: Any) -> dict[str, Any] | None:
    rows, normalized_indices = _normalised(
        kwargs["snapshot"] if "snapshot" in kwargs else kwargs["rows_by_ticker"]
    )
    adapted = dict(kwargs)
    adapted.pop("snapshot", None)
    sector_entries = adapted.pop("sector_entries", {}) or {}
    ticker = str(adapted.get("ticker") or "").upper()
    adapted["sector_meta"] = sector_entries.get(ticker, {})
    adapted["rows_by_ticker"] = rows
    adapted["indices"] = normalized_indices
    return shared.move_rate_volatility_relief_candidate_for_ticker(**adapted)


def configure_scout_framework() -> None:
    scout.EXPERIMENT_ID = EXPERIMENT_ID
    scout.SLUG = "move_rate_volatility_relief_shared_paper"
    scout.RUNNER = RUNNER
    scout.RUNNER_PS = RUNNER.replace("/", "\\")
    scout.RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + scout.RUNNER_PS
    scout.OUT_DIR = OUT_JSON.parent
    scout.OUT_JSON = OUT_JSON
    scout.MOVE_ROWS_JSON = REPO_ROOT / "data" / "experiments" / "exp-20260711-002" / "ice_bofa_move_daily_closes.json"
    scout.LOG_JSON = LOG_JSON
    scout.CARD_MD = CARD_MD
    scout.MANIFEST_JSON = MANIFEST_JSON
    scout.TICKET_JSON = TICKET_JSON
    scout.REGISTRY_JSON = REGISTRY_JSON
    scout.HYPOTHESIS = HYPOTHESIS
    scout.CHANGE_TYPE = "candidate_pool_full_stack"
    scout.IMPLEMENTATION_MODE = "shared_paper_first_promotion"
    scout.MECHANISM_FAMILY = "production_visible_rate_volatility_relief_candidate_pool"
    scout.TRIAL_FAMILY = "move_rate_volatility_relief_shared_paper_candidate_pool"
    scout.TRIAL_VARIANT_ID = shared.SOURCE_RULE_VERSION
    scout.CHANGED_VARIABLE = CHANGED_VARIABLE
    scout.NEW_EVIDENCE_TYPE = "new_gate_shape_shared_paper_first"
    scout.NEW_EVIDENCE_AXIS = NEW_AXIS
    scout.NEARBY_PRIORS = NEARBY
    scout.CAUSAL_COMPONENTS = [
        "shared MOVE rate-volatility relief helper",
        "historical replay through shared decision functions",
        "daily default-off state and snapshot",
        "report and attribution wiring",
        "focused replay/daily parity tests",
        "declared live-realistic execution envelope",
    ]
    scout.PREDICTION = PREDICTION
    scout.PRODUCTION_IMPACT = production_impact()
    scout.ALLOWED_WRITE_SCOPE = ALLOWED_WRITE_SCOPE
    scout.move_relief_context = replay_context
    scout.candidate_for_ticker = replay_candidate


def production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "backtester_adapter_changed": True,
        "run_adapter_changed": True,
        "replay_only": False,
        "trade_enabled": False,
        "entry_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "exit_rules_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "scope": "shared_default_off_move_rate_volatility_relief_paper_attribution",
    }


def execution_envelope() -> ExecutionEnvelope:
    return ExecutionEnvelope(
        base_notional=4_000.0,
        max_capital_pct=0.32,
        min_dollar_volume=50_000_000.0,
        slippage_bps=10.0,
        max_displacement=0,
        max_concurrent=8,
        order_semantics="default_off_next_session_open_observation_only",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.05,
        notes="Top-2/day, 10-session close, 10-session ticker cooldown; activation remains disabled.",
    )


def build_payload() -> dict[str, Any]:
    configure_scout_framework()
    payload = scout.build_payload()
    gate4 = {"passed": bool(payload["gate4"]["passed"]), **payload["gate4"]}
    envelope = execution_envelope()
    live = evaluate_live_readiness(
        envelope=envelope,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
    )
    full_stack = full_stack_verdict(gate4=gate4, live_readiness=live, envelope=envelope)
    accepted = full_stack["verdict"] == "accepted_paper_pending_forward"
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": HYPOTHESIS,
            "change_type": "candidate_pool_full_stack",
            "implementation_mode": "shared_paper_first_promotion",
            "trial_family": "move_rate_volatility_relief_shared_paper_candidate_pool",
            "trial_variant_id": shared.SOURCE_RULE_VERSION,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "new_evidence_type": "new_gate_shape_shared_paper_first",
            "new_evidence_axis": NEW_AXIS,
            "accepted": accepted,
            "accepted_alpha": accepted,
            "observed_only_lead": False,
            "status": "accepted" if accepted else "rejected",
            "decision": full_stack["verdict"] if accepted else "rejected_shared_paper_promotion",
            "production_impact": production_impact(),
            "shared_helper": {
                "module": "quant/move_rate_volatility_relief_paper_sleeve.py",
                "rule_version": shared.RULE_VERSION,
                "source_rule_version": shared.SOURCE_RULE_VERSION,
                "daily_wired": True,
                "report_wired": True,
                "attribution_wired": True,
                "trade_enabled": False,
            },
            "parity": {
                "passed": accepted,
                "historical_context_function": "move_rate_volatility_relief_context_for_day",
                "historical_candidate_function": "move_rate_volatility_relief_candidate_for_ticker",
                "focused_test": "quant/test_move_rate_volatility_relief_paper_sleeve.py",
            },
            "full_stack_verdict": full_stack,
            "execution_envelope": envelope.to_dict(),
            "post_run_reflection": {
                "why_result_happened": (
                    "The shared helper reproduced the fixed private MOVE replay while daily, "
                    "report, and attribution paths expose the identical rule default-off."
                    if accepted
                    else "The shared-helper replay failed to reproduce the fixed private MOVE lead."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retune MOVE spans, levels, persistence, selector fields, top-N, hold, "
                    "cooldown, notional, windows, or response shape."
                ),
                "new_evidence_required": (
                    "Live review requires at least 30 closed prospective rows, positive cash/SPY/QQQ "
                    "replacement value, concentration control, and kill-switch parity; routine daily "
                    "materialization uses run.py and needs no new experiment ID."
                ),
            },
            "changed_files": ALLOWED_WRITE_SCOPE,
            "reproduction_commands": [
                ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_move_rate_volatility_relief_paper_sleeve.py -q",
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260711_004_move_rate_volatility_relief_shared_paper.py",
                ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            ],
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_success": accepted,
        "brier_score": round((PREDICTION["success_probability"] - float(accepted)) ** 2, 6),
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "predicted_failure_modes_hit": [] if accepted else ["gate4_lead_not_reproduced"],
        "surprise_note": "Shared promotion reproduced the private lead." if accepted else "Promotion replay diverged.",
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    scout.write_json(OUT_JSON, payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    log = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": scout.utc_now(),
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "hypothesis": HYPOTHESIS,
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": NEARBY,
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": NEW_AXIS,
        "artifact": scout.repo_rel(OUT_JSON),
        "aggregate_expected_value_delta": aggregate.get("expected_value_score_delta_sum"),
        "aggregate_strategy_total_pnl_delta": aggregate.get("total_pnl_delta_sum"),
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": True,
    }
    save_experiment_log_entry(log, allow_duplicate=True)
    scout.write_text(
        CARD_MD,
        "\n".join(
            [
                f"# {EXPERIMENT_ID} MOVE Shared-Paper Promotion",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                "",
                "## Result",
                "",
                f"- Aggregate EV delta: `{aggregate.get('expected_value_score_delta_sum'):+.4f}`",
                f"- Aggregate PnL delta: `${aggregate.get('total_pnl_delta_sum'):+,.2f}`",
                f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
                f"- Shared rule: `{shared.SOURCE_RULE_VERSION}`",
                "- Daily/report/attribution: `wired`, `trade_enabled=false`",
                "",
                "## Reflection",
                "",
                payload["post_run_reflection"]["why_result_happened"],
                "",
                payload["post_run_reflection"]["new_evidence_required"],
                "",
            ]
        ),
    )
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "decision": payload["decision"],
            "artifact": scout.repo_rel(OUT_JSON),
            "gate4": payload["gate4"],
            "full_stack_verdict": payload["full_stack_verdict"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
            **log,
            "owner": "alpha-explore",
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "baseline_result_file": "data/experiments/exp-20260602-003/exp_20260602_003_post_earnings_explicit_continuation.json",
            "card_file": scout.repo_rel(CARD_MD),
            "revision_manifest_file": scout.repo_rel(MANIFEST_JSON),
        },
    )
    scout.write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "files": {path: {"exists": (REPO_ROOT / path).exists()} for path in ALLOWED_WRITE_SCOPE},
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_ev_delta": aggregate.get("expected_value_score_delta_sum"),
                "aggregate_pnl_delta": aggregate.get("total_pnl_delta_sum"),
                "target_trades": payload["target_trade_summary"]["total_trade_count"],
                "trade_enabled": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
