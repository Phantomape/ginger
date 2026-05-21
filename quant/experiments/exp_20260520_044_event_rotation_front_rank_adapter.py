"""exp-20260520-044: promote event-rotation front-rank field to adapter.

Alpha search. This run keeps the exp-20260520-043 single causal variable:
extra paper notional for rotation_breakout_leadership event rows whose
state-surface rank is in the top quintile. The new thing being validated is
that the positive replay field is now represented in the shared default-off
event adapter and surfaced in production reporting without enabling orders.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260520_043_event_rotation_front_rank_quality_tilt as prior


EXPERIMENT_ID = "exp-20260520-044"
EXPERIMENT_SLUG = "event_rotation_front_rank_adapter"

REPO_ROOT = prior.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

from event_sleeve_bundle import build_event_sleeve_bundle_snapshot

OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _parent():
    return prior._parent()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _adapter_contract() -> dict[str, Any]:
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-20",
        form4_event_queue={
            "rule_version": "adapter_contract_form4_rule",
            "candidates": [
                {
                    "ticker": "LITE",
                    "usable_trade_date": "2026-05-20",
                    "counterfactual": {"alternatives": [{"type": "cash"}]},
                },
                {
                    "ticker": "SLOW",
                    "usable_trade_date": "2026-05-20",
                    "counterfactual": {"alternatives": [{"type": "cash"}]},
                },
            ],
        },
        state_surface_queue={
            "scored_candidate_count": 10,
            "scored_candidates": [
                {
                    "ticker": "LITE",
                    "rank": 1,
                    "score": 1.24,
                    "surface": "rotation_breakout_leadership",
                    "decision_date": "2026-05-20",
                },
                {
                    "ticker": "SLOW",
                    "rank": 5,
                    "score": 0.71,
                    "surface": "rotation_breakout_leadership",
                    "decision_date": "2026-05-20",
                },
            ],
        },
    )
    rows = {row["ticker"]: row for row in snapshot["candidates"]}
    front = rows["LITE"]["state_surface_addon"]
    slower = rows["SLOW"]["state_surface_addon"]
    checks = {
        "front_rank_scalar_4x": front.get("scalar") == 4.0,
        "front_rank_reason": front.get("reason")
        == "eligible_front_rank_rotation_breakout_positive_state_surface",
        "front_rank_pct_known": front.get("state_rank_pct") == 0.1,
        "non_front_rotation_stays_3x": slower.get("scalar") == 3.0,
        "orders_remain_disabled": snapshot["trade_enabled"] is False
        and snapshot["trade_plan"]["trade_enabled"] is False
        and rows["LITE"]["alters_orders"] is False,
        "summary_surfaces_field": snapshot["state_surface_addon"][
            "front_rank_rotation_tilt_candidate_count"
        ]
        == 1,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "front_rank_addon": front,
        "non_front_rotation_addon": slower,
        "summary": snapshot["state_surface_addon"],
        "trade_plan_status": snapshot["trade_plan"]["status"],
    }


def build_payload() -> dict[str, Any]:
    prior_payload = prior.build_payload()
    best = prior_payload["best_variant"]
    gate = prior_payload["delta_metrics"]["variant_vs_event_rotation_300"][best]
    adapter = _adapter_contract()
    accepted = bool(gate["passed"] and adapter["passed"])
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    decision = (
        "accepted_default_off_event_rotation_front_rank_adapter"
        if accepted
        else "rejected_event_rotation_front_rank_adapter"
    )
    rejection_reason = None
    if not accepted:
        rejection_reason = (
            f"Gate passed={gate['passed']} adapter_contract_passed={adapter['passed']}; "
            "do not keep the shared adapter field unless both are true."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "shared_default_off_event_adapter_field",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "trial_family": "event_rotation_replacement_value_maturation",
        "trial_variant_id": "front_rank_quality_adapter",
        "changed_variable": "front_rank_rotation_event_paper_notional_tilt_shared_adapter",
        "prior_trial_count": 10,
        "nearby_prior_experiments": [
            *prior_payload["nearby_prior_experiments"],
            "exp-20260520-043",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "shared_adapter_parity_for_prior_replay_field",
        "hypothesis": (
            "The exp-20260520-043 front-rank event-rotation quality field is "
            "worth promoting from replay-only evidence into the shared "
            "default-off event adapter, because it improves the three canonical "
            "windows versus the 3.0x rotation baseline and can be surfaced in "
            "production reporting without live order authority."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / event-quality",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Continues the preferred event-rotation replacement-value "
                "maturation lane, using one production-visible state-rank field "
                "rather than another LLM, SEC, broad-market, or state-surface "
                "threshold retune."
            ),
        },
        "single_causal_variable": (
            "shared default-off adapter notional scalar for "
            "rotation_breakout_leadership event rows with state_rank_pct <= 0.20"
        ),
        "parameters": {
            "baseline_experiment": "exp-20260520-042",
            "evidence_experiment": "exp-20260520-043",
            "front_rank_max_pct": 0.20,
            "front_rank_rotation_tilt_scalar": 4.0,
            "rotation_other_rank_scalar": 3.0,
            "eligible_non_rotation_scalar": 2.0,
            "base_event_notional_usd": 10_000.0,
            "hold_days": prior_payload["parameters"]["hold_days"],
            "round_trip_cost_pct": prior_payload["parameters"]["round_trip_cost_pct"],
            "locked_variables": prior_payload["parameters"]["locked_variables"],
            "anti_js": "No JavaScript was used.",
        },
        "date_range": prior_payload["date_range"],
        "market_regime_summary": prior_payload["market_regime_summary"],
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Promote the strongest current event-rotation field into the "
                "shared default-off adapter; category is capital allocation."
            ),
            "2_history_check": (
                "exp-20260520-042 revalidated event rotation; exp-20260520-043 "
                "found the top-quintile state-rank field positive versus the "
                "3.0x baseline. Source-specific event rotation had failed in "
                "exp-20260516-030."
            ),
            "3_single_causal_variable": (
                "Only adapter exposure of the front-rank rotation notional field "
                "changes; live/core entries, exits, ranking, sizing, news, and "
                "LLM behavior remain fixed."
            ),
            "4_acceptance_standard": (
                "Use docs/backtesting.md three fixed windows from exp043 plus a "
                "shared-adapter contract proving production reporting sees the "
                "same scalar and orders remain disabled."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260520_044_event_rotation_front_rank_adapter.py"
            ),
        },
        "historical_experiment_check": prior_payload["historical_experiment_check"],
        "backtest_protocol": {
            **prior_payload["backtest_protocol"],
            "adapter_contract": (
                "event_sleeve_bundle.build_event_sleeve_bundle_snapshot must "
                "surface scalar=4.0 for front-rank rotation rows and keep "
                "trade_plan blocked unless the explicit forward/live gate is "
                "enabled."
            ),
        },
        "gate1": prior_payload["gate1"],
        "gate2": {
            **prior_payload["gate2"],
            "adapter_contract": adapter,
            "passed": bool(prior_payload["gate2"]["passed"] and adapter["passed"]),
        },
        "gate3": prior_payload["gate3"],
        "gate4": {
            **prior_payload["gate4"],
            "adapter_contract_passed": adapter["passed"],
            "passed": bool(gate["passed"] and adapter["passed"]),
        },
        "before_metrics": {
            "event_rotation_300_baseline": prior_payload["before_metrics"][
                "event_rotation_300_baseline"
            ],
        },
        "after_metrics": {best: prior_payload["after_metrics"][best]},
        "delta_metrics": prior_payload["delta_metrics"],
        "best_variant": best,
        "expected_value_score_delta": gate["delta"]["aggregate_ev_delta"],
        "total_pnl_delta": gate["delta"]["aggregate_pnl_delta"],
        "selection": prior_payload["selection"][best],
        "adapter_contract": adapter,
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "parity_test_added": True,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "scope": "default_off_event_overlay_bundle_paper_attribution",
            "live_orders_enabled": False,
            "forward_gate_still_required": True,
        },
        "llm_metrics": prior_payload["llm_metrics"],
        "decision_rationale": (
            "Accepted as shared default-off paper attribution only. The adapter "
            "now surfaces the same front-rank event-rotation scalar validated in "
            "exp043, while live/default orders remain blocked."
            if accepted
            else rejection_reason
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "Collect closed forward replacement-value outcomes before any "
            "trade-enabled event adapter."
            if accepted
            else "Roll back the shared adapter field and require new evidence."
        ),
        "why_not_other_attractive_points": prior_payload[
            "why_not_other_attractive_points"
        ],
        "risk_of_change": (
            "Historical target evidence is still thin: three target trades across "
            "two windows. This commit keeps the field default-off and non-ordering."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(REPO_ROOT / "quant" / "event_sleeve_bundle.py"),
            _repo_rel(REPO_ROOT / "quant" / "report_generator.py"),
            _repo_rel(REPO_ROOT / "quant" / "test_event_sleeve_bundle.py"),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["gate4"]
    baseline = payload["before_metrics"]["event_rotation_300_baseline"]
    after = payload["after_metrics"][best]
    lines = [
        f"# {EXPERIMENT_ID} Event-Rotation Front-Rank Adapter",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search. Promotes the exp043 front-rank event-rotation field "
            "into shared default-off paper attribution; no live/default orders "
            "are enabled."
        ),
        "",
        "## Gate 4 Result",
        "",
        "| Window | Baseline EV | Adapter EV | Delta EV | Baseline PnL | Adapter PnL | Delta PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in _parent().base.WINDOWS:
        delta = gate["delta"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=baseline[label]["expected_value_score"],
                aev=after[label]["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=baseline[label]["total_pnl"],
                apnl=after[label]["total_pnl"],
                dpnl=delta["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Adapter Contract",
            "",
            "```json",
            json.dumps(payload["adapter_contract"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Shared default-off adapter/reporting changed. Core entries, "
                "ranking, sizing, exits, LLM/news, and live/default orders are "
                "unchanged; forward gate remains required before any trade adapter."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "lane",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "hypothesis",
        "alpha_hypothesis",
        "single_causal_variable",
        "parameters",
        "date_range",
        "market_regime_summary",
        "gate_questions",
        "historical_experiment_check",
        "backtest_protocol",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "best_variant",
        "expected_value_score_delta",
        "total_pnl_delta",
        "selection",
        "adapter_contract",
        "production_impact",
        "llm_metrics",
        "decision_rationale",
        "rejection_reason",
        "next_action",
        "why_not_other_attractive_points",
        "risk_of_change",
        "related_files",
        "anti_js",
    ]
    return {key: payload[key] for key in keys}


def persist(payload: dict[str, Any]) -> None:
    parent = _parent()
    parent._write_json(OUT_JSON, payload)
    compact = _compact_log(payload)
    parent._write_json(LOG_JSON, compact)
    parent._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event-rotation front-rank adapter",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "next_action": payload["next_action"],
        },
    )
    parent._write_text(ARTIFACT_MD, _artifact_markdown(payload))

    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    lines.append(json.dumps(parent._safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _parent()._safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "best_variant": payload["best_variant"],
                    "ev_delta_vs_baseline": payload["expected_value_score_delta"],
                    "pnl_delta_vs_baseline": payload["total_pnl_delta"],
                    "adapter_contract_passed": payload["adapter_contract"]["passed"],
                    "out_json": str(OUT_JSON),
                    "anti_js": "No JavaScript was used.",
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
