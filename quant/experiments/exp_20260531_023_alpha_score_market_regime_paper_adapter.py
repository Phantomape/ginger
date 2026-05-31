"""exp-20260531-023: alpha-score market-regime paper adapter.

This alpha search promotes the accepted exp-20260531-021 lead into a shared
production-visible, default-off paper adapter. The candidate source stays fixed:
full-universe PIT ``alpha_score`` top-decile, top-1/day, SPY/IWM risk-appetite
gate, 20-trading-day hold, and $4,000 paper notional.

The single changed variable is the production/replay boundary: add a default-off
adapter and attribution/report wiring while keeping live/default orders disabled.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional as source


framework = source.framework

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260531-023"
STEM = "alpha_score_market_regime_paper_adapter"
TRIAL_FAMILY = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
CHANGED_VARIABLE = "alpha_score_market_regime_safe_notional_shared_adapter_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_023_{STEM}.json"
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
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "accepted_alpha_score_market_regime_default_off_adapter"
        if gate4["passed"]
        else "rejected_alpha_score_market_regime_default_off_adapter"
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Promoting the accepted exp-20260531-021 alpha_score "
                "market-regime safe-notional candidate source into a shared "
                "production-visible default-off paper adapter should preserve "
                "the 3-window EV lead while removing the production/backtest "
                "consistency blocker for forward observation."
            ),
            "change_type": "default_off_paper_adapter",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "candidate_pool_expansion",
            "trial_variant_id": CHANGED_VARIABLE,
            "prior_trial_count": 8,
            "nearby_prior_experiments": [
                "exp-20260531-005",
                "exp-20260531-016",
                "exp-20260531-021",
            ],
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": "shared_production_replay_adapter",
            "prediction": {
                "success_probability": 0.65,
                "expected_ev_delta": 1.64,
                "expected_pnl_delta": 32770.52,
                "main_failure_modes": [
                    "adapter_mismatch",
                    "production_wiring_gap",
                    "canonical_replay_drift",
                ],
                "confidence_reason": (
                    "exp-20260531-021 already passed Gate 4 by +20.82% "
                    "aggregate EV. This run changes only the production-visible "
                    "default-off adapter boundary."
                ),
                "recorded_at": "2026-05-31T18:07:26+00:00",
                "brier_score": round((0.65 - actual_success) ** 2, 6),
            },
            "parameters": {
                **payload["parameters"],
                "source_definition_fixed_from": "exp-20260531-021",
                "adapter_rule_version": "alpha_score_market_regime_safe_notional_shared_v1",
                "changed_only": [
                    "add quant/alpha_score_market_regime_paper_sleeve.py as a shared default-off adapter",
                    "wire the adapter into quant/run.py daily artifacts and report surfaces",
                    "add parity tests proving trade_enabled=false and production orders unchanged",
                    "keep alpha_score weights, market gate, top-1/day, 20-day hold, and $4,000 notional fixed",
                ],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / risk allocation: exp021 is the strongest "
                    "current free-data candidate-pool lead; a shared default-off "
                    "adapter should make it production-observable without "
                    "changing orders."
                ),
                "2_history_check": {
                    "exp-20260531-005": (
                        "Raw full-universe alpha_score top-1 was rejected for "
                        "drawdown/concentration risk."
                    ),
                    "exp-20260531-016": (
                        "Adding the SPY/IWM market gate improved EV but failed "
                        "the drawdown guard at $10k notional."
                    ),
                    "exp-20260531-021": (
                        "$4k safe notional passed all three standard windows "
                        "with aggregate EV +1.6439 (+20.82%) and PnL "
                        "+$32,770.52, but required a shared adapter before "
                        "promotion."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md three-window before/after as "
                    "exp021 plus adapter parity tests showing default-off, "
                    "trade_enabled=false, and no production order changes."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260531_023_alpha_score_market_regime_paper_adapter.py"
                ),
            },
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "trade_enabled": False,
                "shared_adapter_added": True,
                "run_adapter_changed": True,
                "report_adapter_changed": True,
                "backtester_adapter_changed": False,
                "parity_test_added": True,
                "adapter_module": "quant/alpha_score_market_regime_paper_sleeve.py",
                "parity_note": (
                    "The adapter writes only default-off paper candidates, "
                    "ledger state, daily artifact fields, and report text. "
                    "Core entry ranking, sizing, exits, LLM/news, watchlists, "
                    "and order paths do not read it."
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
                    "candidate payloads and sleeve snapshots carry trade_enabled=false",
                    "production_impact.production_orders_changed is false",
                    "stale as-of prices cannot fill pending paper entries",
                    "default-off attribution surfaces the adapter as blocked until forward rows close",
                ],
            },
            "interpretation": (
                "Accepted as a production-visible default-off paper adapter. "
                "The 3-window economics are the accepted exp021 replay result; "
                "this run does not activate live/default orders. The next "
                "evidence is forward replacement-value rows from the shared "
                "adapter, not another threshold/notional retune."
                if gate4["passed"]
                else (
                    "Rejected. Do not promote the adapter because the fixed "
                    "exp021 three-window economics did not reproduce."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Collect forward paper rows from the shared adapter; do not "
                "enable live/default orders or retune alpha_score thresholds "
                "until forward replacement value is reviewable."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["production_parity"]["source_replay_artifact"] = (
        "experiments/artifacts/"
        "exp-20260531-021_full_universe_alpha_score_market_regime_safe_notional.md"
    )
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
        "quant/alpha_score_market_regime_paper_sleeve.py",
        "quant/test_alpha_score_market_regime_paper_sleeve.py",
        "quant/run.py",
        "quant/report_generator.py",
        "quant/default_off_alpha_attribution.py",
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            "# exp-20260531-023 Alpha-Score Market-Regime Paper Adapter",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: add a shared production-visible default-off adapter for the fixed exp021 alpha_score market-regime $4,000 paper source. No score weights, thresholds, hold period, market gate, core ranking, sizing, exits, LLM/news, watchlists, or live orders changed.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max drawdown delta max: `{aggregate['max_drawdown_delta_max']}`",
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
            json.dumps(gate4, indent=2, sort_keys=True),
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
        "title": "Alpha-score market-regime paper adapter",
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
