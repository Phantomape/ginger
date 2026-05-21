"""exp-20260521-006: promote event governance-source quality adapter.

Alpha search. Promotes the accepted replay-only
`sec_governance_procedural` source-quality paper notional scalar into the
shared default-off event overlay adapter. This still does not enable live or
default orders.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260521_005_event_governance_source_quality as scout


EXPERIMENT_ID = "exp-20260521-006"
EXPERIMENT_SLUG = "event_governance_source_adapter"

REPO_ROOT = scout.REPO_ROOT
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
    return scout._parent()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _adapter_contract() -> dict[str, Any]:
    counterfactual = {"frozen": True, "alternatives": [{"type": "cash"}]}
    snapshot = build_event_sleeve_bundle_snapshot(
        as_of="2026-05-21",
        sec_governance_event_queue={
            "rule_version": "sec_governance_rule",
            "candidates": [
                {
                    "ticker": "GOV",
                    "usable_trade_date": "2026-05-21",
                    "counterfactual": counterfactual,
                },
                {
                    "ticker": "GBRD",
                    "usable_trade_date": "2026-05-21",
                    "counterfactual": counterfactual,
                },
            ],
        },
        sec_negative_event_queue={
            "rule_version": "sec_negative_rule",
            "candidates": [
                {
                    "ticker": "NBRD",
                    "usable_trade_date": "2026-05-21",
                    "counterfactual": counterfactual,
                }
            ],
        },
        state_surface_queue={
            "scored_candidate_count": 8,
            "scored_candidates": [
                {
                    "ticker": "GOV",
                    "rank": 6,
                    "score": 0.91,
                    "surface": "balanced_state_leadership",
                    "breadth_bucket": "mixed_breadth",
                    "decision_date": "2026-05-21",
                },
                {
                    "ticker": "GBRD",
                    "rank": 3,
                    "score": 1.03,
                    "surface": "broad_breadth_trend_persistence",
                    "breadth_bucket": "broad_breadth",
                    "decision_date": "2026-05-21",
                },
                {
                    "ticker": "NBRD",
                    "rank": 4,
                    "score": 0.88,
                    "surface": "broad_breadth_trend_persistence",
                    "breadth_bucket": "broad_breadth",
                    "decision_date": "2026-05-21",
                },
            ],
        },
    )
    by_ticker = {row["ticker"]: row for row in snapshot["candidates"]}
    gov = by_ticker["GOV"]["state_surface_addon"]
    gov_broad = by_ticker["GBRD"]["state_surface_addon"]
    neg_broad = by_ticker["NBRD"]["state_surface_addon"]
    summary = snapshot["state_surface_addon"]
    checks = {
        "generic_governance_source_2x": (
            gov.get("source_quality_tilt") is True
            and gov.get("state_surface_scalar") == 1.0
            and gov.get("scalar") == 2.0
            and by_ticker["GOV"].get("paper_event_notional_usd") == 20_000.0
        ),
        "broad_governance_source_stacks_to_5x": (
            gov_broad.get("broad_breadth_tilt") is True
            and gov_broad.get("source_quality_tilt") is True
            and gov_broad.get("state_surface_scalar") == 2.5
            and gov_broad.get("scalar") == 5.0
            and by_ticker["GBRD"].get("paper_event_notional_usd") == 50_000.0
        ),
        "negative_source_does_not_get_governance_tilt": (
            neg_broad.get("source_quality_tilt") is False
            and neg_broad.get("scalar") == 2.5
        ),
        "orders_stay_disabled": (
            snapshot.get("trade_enabled") is False
            and snapshot.get("trade_plan", {}).get("trade_enabled") is False
            and all(row.get("alters_orders") is False for row in snapshot["candidates"])
        ),
        "summary_counts_source_quality": (
            summary.get("source_quality_tilt_candidate_count") == 2
            and summary.get("source_quality_tilt_incremental_notional_usd") == 35_000.0
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "snapshot_summary": {
            "candidate_count": snapshot["candidate_count"],
            "deduped_candidate_count": snapshot["deduped_candidate_count"],
            "state_surface_addon": summary,
            "trade_plan_status": snapshot["trade_plan"]["status"],
        },
    }


def _operator_position_field_check() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {
            "path": _repo_rel(path),
            "passed": False,
            "position_count": 0,
            "missing_file": True,
            "missing_entry_date_or_target_price": [],
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        positions = data.get("positions") or []
    elif isinstance(data, list):
        positions = data
    else:
        positions = []
    missing = [
        str(position.get("ticker") or position.get("symbol") or "UNKNOWN")
        for position in positions
        if isinstance(position, dict)
        and (not position.get("entry_date") or not position.get("target_price"))
    ]
    return {
        "path": _repo_rel(path),
        "passed": not missing,
        "position_count": len(positions),
        "missing_entry_date_or_target_price": missing,
    }


def build_payload() -> dict[str, Any]:
    payload = deepcopy(scout.build_payload())
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    adapter_contract = _adapter_contract()
    operator_position_field_check = _operator_position_field_check()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": timestamp,
            "status": "accepted_default_off_event_governance_source_quality_adapter",
            "decision": "accepted_default_off_event_governance_source_quality_adapter",
            "change_type": "event_source_quality_allocation_adapter",
            "trial_variant_id": "sec_governance_procedural_source_quality_adapter",
            "changed_variable": "event_sec_governance_procedural_paper_notional_scalar",
            "prior_trial_count": 15,
            "nearby_prior_experiments": [
                *payload["nearby_prior_experiments"],
                "exp-20260521-005",
            ],
            "single_causal_variable": (
                "shared default-off paper-notional scalar for event overlay rows "
                "whose source is sec_governance_procedural"
            ),
            "hypothesis": (
                "The positive exp-20260521-005 governance-source quality scout "
                "should be retained by moving its 2.0x paper notional scalar "
                "into the shared default-off event adapter, preserving production "
                "visibility without enabling live/default orders."
            ),
            "adapter_contract": adapter_contract,
            "production_impact": {
                "shared_policy_changed": True,
                "backtester_adapter_changed": False,
                "run_adapter_changed": True,
                "replay_only": False,
                "parity_test_added": True,
                "production_signal_path_changed": True,
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_exits": False,
                "alters_orders": False,
                "live_orders_enabled": False,
                "scope": "default_off_event_overlay_bundle_paper_attribution",
            },
            "decision_rationale": (
                "Accepted as a shared default-off paper adapter change. "
                "The prior scout cleared the three canonical windows and the "
                "adapter contract proves the production-visible bundle now applies "
                "the same source-quality scalar while keeping orders disabled."
            ),
            "next_action": (
                "Keep live/default capital disabled. Continue collecting closed "
                "forward replacement-value evidence before any trade-enabled event "
                "bundle experiment."
            ),
            "risk_of_change": (
                "No live orders, ranking, core sizing, exits, or source capacity "
                "changed. Risk is paper attribution overfit until forward outcomes "
                "mature."
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
                "quant/event_sleeve_bundle.py",
                "quant/test_event_sleeve_bundle.py",
                "quant/report_generator.py",
                "docs/production_backtest_parity.md",
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(ARTIFACT_MD),
                _repo_rel(EXPERIMENT_LOG),
            ],
        }
    )
    payload["gate2"]["operator_position_field_check"] = operator_position_field_check
    payload["gate2"]["passed"] = bool(
        payload["gate2"].get("passed") and operator_position_field_check["passed"]
    )
    payload["parameters"]["adapter_promotion"] = {
        "source": "sec_governance_procedural",
        "paper_notional_scalar": 2.0,
        "live_orders_enabled": False,
        "forward_gate_still_required": True,
    }
    payload["gate4"]["adapter_contract_passed"] = adapter_contract["passed"]
    payload["gate4"]["passed"] = bool(payload["gate4"]["passed"] and adapter_contract["passed"])
    payload["anti_js"] = "No JavaScript was used."
    return payload


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["gate4"]
    baseline = payload["before_metrics"][scout.BASELINE_VARIANT]
    after = payload["after_metrics"][best]
    lines = [
        f"# {EXPERIMENT_ID} Event Governance-Source Adapter",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Promotes the exp-20260521-005 governance-source quality scout into the shared default-off event adapter.",
        "",
        "## Gate 4",
        "",
        "| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |",
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
            "Shared default-off event adapter/reporting changed. Live/default orders remain disabled.",
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
        "source_coverage",
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
    compact = {key: payload[key] for key in keys}
    compact["after_metrics"] = {
        payload["best_variant"]: payload["after_metrics"][payload["best_variant"]]
    }
    compact["selection"] = payload["selection"][payload["best_variant"]]
    return compact


def persist(payload: dict[str, Any]) -> None:
    parent = _parent()
    parent._write_json(OUT_JSON, payload)
    compact = _compact_log(payload)
    parent._write_json(LOG_JSON, compact)
    parent._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event governance-source adapter",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "adapter_contract_passed": payload["adapter_contract"]["passed"],
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
                    "windows_ev_improved": payload["gate4"]["delta"][
                        "windows_ev_improved"
                    ],
                    "windows_ev_regressed": payload["gate4"]["delta"][
                        "windows_ev_regressed"
                    ],
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
