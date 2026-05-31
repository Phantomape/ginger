"""exp-20260531-025: alpha-score source-consensus shared adapter.

This alpha search promotes the positive exp-20260531-024 replay lead into the
shared default-off alpha-score market-regime paper adapter. The economic source
stays fixed: exp024's 1.25x paper-notional support when an accepted alpha-score
candidate also appears in accepted FINRA/IWM or VBB paper sources on the same
signal date.

The single changed variable is the production/replay boundary. Live orders,
core entries, ranking, sizing, exits, LLM, and news behavior remain unchanged.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_024_alpha_score_source_consensus_support as source


framework = source.framework

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260531-025"
STEM = "alpha_score_source_consensus_adapter"
TRIAL_FAMILY = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
CHANGED_VARIABLE = "alpha_score_source_consensus_shared_adapter_v1"
SOURCE_CONSENSUS_RULE_VERSION = "alpha_score_market_regime_source_consensus_support_1p25_v1"
ADAPTER_RULE_VERSION = "alpha_score_market_regime_safe_notional_shared_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_025_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _build_adapter_payload() -> dict[str, Any]:
    source._patch_framework()
    payload = source._postprocess_payload(framework._build_payload())
    gate4 = payload["gate4"]
    accepted_comparison = payload.get("accepted_baseline_comparison") or {}
    incremental_passed = bool(
        accepted_comparison.get("available")
        and accepted_comparison.get("aggregate_expected_value_score_delta_vs_exp021", 0) > 0
        and accepted_comparison.get("windows_ev_regressed_vs_exp021", 0) == 0
        and accepted_comparison.get("windows_pnl_regressed_vs_exp021", 0) == 0
    )
    actual_success = 1 if gate4["passed"] and incremental_passed else 0
    decision = (
        "accepted_alpha_score_source_consensus_default_off_adapter"
        if actual_success
        else "rejected_alpha_score_source_consensus_default_off_adapter"
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Promoting the positive exp-20260531-024 alpha_score "
                "source-consensus paper-notional support into the shared "
                "default-off adapter should preserve the three-window EV lead "
                "while removing the production/backtest consistency blocker."
            ),
            "change_type": "default_off_paper_adapter",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "candidate_pool_expansion",
            "trial_variant_id": CHANGED_VARIABLE,
            "prior_trial_count": 9,
            "nearby_prior_experiments": [
                "exp-20260531-021",
                "exp-20260531-023",
                "exp-20260531-024",
                "exp-20260530-007",
                "exp-20260529-004",
            ],
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": "shared_production_replay_adapter_for_positive_replay_lead",
            "prediction": {
                "success_probability": 0.68,
                "expected_ev_delta": 1.7609,
                "expected_pnl_delta": 35110.96,
                "main_failure_modes": [
                    "adapter_mismatch",
                    "production_wiring_gap",
                    "source_snapshot_ordering_gap",
                    "canonical_replay_drift",
                ],
                "confidence_reason": (
                    "exp-20260531-024 already passed the three-window Gate 4; "
                    "this run changes only the shared default-off adapter and "
                    "parity/report surface."
                ),
                "recorded_at": "2026-05-31T20:07:34+00:00",
                "brier_score": round((0.68 - actual_success) ** 2, 6),
            },
            "parameters": {
                **payload["parameters"],
                "source_replay_fixed_from": "exp-20260531-024",
                "adapter_rule_version": ADAPTER_RULE_VERSION,
                "source_consensus_rule_version": SOURCE_CONSENSUS_RULE_VERSION,
                "source_consensus_notional_scalar": 1.25,
                "baseline_safe_paper_notional_usd": 4000.0,
                "source_consensus_paper_notional_usd": 5000.0,
                "changed_only": [
                    "add source-consensus support fields to quant/alpha_score_market_regime_paper_sleeve.py",
                    "wire run.py so the alpha-score sleeve receives same-day VBB and FINRA/IWM paper snapshots",
                    "surface the same field in report/default-off attribution outputs",
                    "keep alpha_score weights, market gate, top-1/day, 20-day hold, base notional, core logic, LLM/news, and live orders fixed",
                ],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "capital allocation / candidate_pool: cross-source "
                    "agreement between accepted alpha_score, FINRA/IWM, and "
                    "VBB free-data sleeves identifies higher-confidence "
                    "default-off paper candidates."
                ),
                "2_history_check": {
                    "exp-20260531-021": (
                        "Accepted the fixed alpha_score market-regime source at "
                        "$4,000 notional with +1.6439 aggregate EV."
                    ),
                    "exp-20260531-023": (
                        "Promoted that route into a shared default-off adapter."
                    ),
                    "exp-20260531-024": (
                        "Replay-only source-consensus support improved all "
                        "three windows and passed concentration/drawdown gates, "
                        "but required a shared adapter."
                    ),
                    "exp-20260530-007": "Accepted FINRA/IWM/cooldown source.",
                    "exp-20260529-004": "Accepted VBB cost/liquidity source.",
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md three-window before/after replay "
                    "from exp024 plus adapter parity tests showing "
                    "trade_enabled=false and production_orders_changed=false."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260531_025_alpha_score_source_consensus_adapter.py"
                ),
            },
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "trade_enabled": False,
                "shared_adapter_changed": True,
                "run_adapter_changed": True,
                "report_adapter_changed": True,
                "backtester_adapter_changed": False,
                "parity_test_added": True,
                "adapter_module": "quant/alpha_score_market_regime_paper_sleeve.py",
                "source_snapshots": [
                    "VOLUME_BREADTH_BREAKOUT_PAPER",
                    "FINRA_IWM_CONFIRMED_PAPER",
                ],
                "parity_note": (
                    "Production computes the source-consensus support from the "
                    "same-day default-off VBB and FINRA/IWM paper snapshots "
                    "before alpha-score pending entries are created. The field "
                    "only changes paper notional and metadata."
                ),
            },
            "production_impact": {
                "shared_policy_changed": True,
                "backtester_adapter_changed": False,
                "run_adapter_changed": True,
                "report_adapter_changed": True,
                "replay_only": False,
                "parity_test_added": True,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "trade_enabled": False,
                "scope": "default_off_alpha_score_market_regime_paper_attribution",
            },
            "parity_tests": {
                "focused_command": (
                    ".venv\\Scripts\\python.exe -m pytest "
                    "quant\\test_alpha_score_market_regime_paper_sleeve.py -q"
                ),
                "assertions": [
                    "source-consensus candidates receive 1.25x paper notional only",
                    "base safe_paper_notional_usd remains $4,000",
                    "candidate payloads and sleeve snapshots carry trade_enabled=false",
                    "production_impact.production_orders_changed is false",
                    "default-off attribution exposes source-consensus support counts",
                ],
            },
            "interpretation": (
                "Accepted as a production-visible default-off adapter increment. "
                "The 3-window economics are the accepted exp024 replay result; "
                "this run does not activate live/default orders. The next "
                "evidence is forward replacement-value rows from the shared "
                "adapter, not another alpha_score threshold/notional retune."
                if actual_success
                else (
                    "Rejected. Do not promote the source-consensus adapter "
                    "because the exp024 economics or incremental comparison "
                    "did not reproduce."
                )
            ),
            "rejection_reason": None
            if actual_success
            else "Gate 4 or incremental exp021 comparison failed.",
            "next_evidence_needed": (
                "Collect forward paper rows with replacement value versus cash "
                "and same-day core candidates; do not enable live/default "
                "orders or retune alpha_score thresholds until forward evidence "
                "passes a separate activation gate."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
        "quant/alpha_score_market_regime_paper_sleeve.py",
        "quant/run.py",
        "quant/report_generator.py",
        "quant/default_off_alpha_attribution.py",
        "quant/test_alpha_score_market_regime_paper_sleeve.py",
        "docs/production_backtest_parity.md",
        "docs/data_edge_context_layers.md",
        "docs/alpha-optimization-playbook.md",
        framework.base._repo_rel(OUT_JSON),
        framework.base._repo_rel(BEFORE_AGG_JSON),
        framework.base._repo_rel(AFTER_AGG_JSON),
        framework.base._repo_rel(LOG_JSON),
        framework.base._repo_rel(TICKET_JSON),
        framework.base._repo_rel(CARD_MD),
        framework.base._repo_rel(ARTIFACT_MD),
        framework.base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Consensus trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    consensus = payload["source_consensus_summary"]
    for label in framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {support} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                support=consensus["by_window"][label]["trade_count"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            "# exp-20260531-025 Alpha-Score Source-Consensus Adapter",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: promote exp024's source-consensus 1.25x paper-notional support into the shared default-off adapter. No live orders, core ranking, sizing, exits, LLM/news, score weights, top-N, market gate, hold period, or base notional changed.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta vs core: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta vs core: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- incremental EV vs accepted exp021: `{payload['accepted_baseline_comparison']['aggregate_expected_value_score_delta_vs_exp021']}`",
            f"- incremental PnL vs accepted exp021: `${payload['accepted_baseline_comparison']['aggregate_total_pnl_delta_vs_exp021']}`",
            f"- supported trades: `{consensus['supported_trade_count']}` across `{len(consensus['supported_windows'])}` windows",
            f"- incremental support PnL: `${consensus['incremental_support_pnl']}`",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Adapter Parity",
            "",
            "```json",
            json.dumps(payload["production_parity"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Alpha-score source-consensus adapter",
        "status": payload["status"],
        "decision": payload["decision"],
        "json": framework.base._repo_rel(OUT_JSON),
        "card": framework.base._repo_rel(CARD_MD),
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "before_aggregate": payload["judge_before_aggregate"],
        "after_aggregate": payload["judge_after_aggregate"],
        "summary": payload["interpretation"],
        "completed_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "failed_reasons": payload["gate4"]["failed_reasons"],
            "result_file": framework.base._repo_rel(OUT_JSON),
            "card_file": framework.base._repo_rel(CARD_MD),
            "artifact_file": framework.base._repo_rel(ARTIFACT_MD),
            "gate4_passed": payload["gate4"]["passed"],
            "delta_metrics": {
                "expected_value_score": payload["expected_value_score_delta"],
                "total_pnl": payload["total_pnl_delta"],
                "max_drawdown_pct": payload["delta_metrics"]["aggregate"][
                    "max_drawdown_delta_max"
                ],
            },
            "production_orders_changed": False,
            "trade_enabled": False,
        },
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    report = _build_report(payload)
    framework.base._write_text(CARD_MD, report)
    framework.base._write_text(ARTIFACT_MD, report)
    framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_adapter_payload()
    _persist(payload)
    print(
        json.dumps(
            framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "incremental_vs_exp021": payload["accepted_baseline_comparison"],
                    "gate4": payload["gate4"],
                    "production_orders_changed": False,
                    "trade_enabled": False,
                    "card": framework.base._repo_rel(CARD_MD),
                    "artifact": framework.base._repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
