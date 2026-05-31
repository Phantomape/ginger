"""exp-20260531-021: alpha-score market-regime safe notional.

This alpha search keeps the exp-20260531-016 candidate definition fixed:
full-universe PIT ``alpha_score`` top-decile, top-1/day, 20-trading-day hold,
and the SPY/IWM risk-appetite market gate. The single changed variable is the
default-off paper risk budget: $4,000 per paper candidate instead of $10,000.

Core signal generation, alpha_score weights, market-gate inputs, ranking,
exits, LLM/news replay, watchlists, and live/default orders are unchanged. No
JavaScript is used.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_016_full_universe_alpha_score_market_regime_candidate_pool as source


framework = source.framework

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260531-021"
STEM = "full_universe_alpha_score_market_regime_safe_notional"
TRIAL_FAMILY = "full_universe_alpha_score_candidate_pool_safe_risk_budget"
CHANGED_VARIABLE = "full_universe_alpha_score_market_regime_safe_notional_0p40_v1"
RULE_VERSION = "full_universe_alpha_score_market_regime_safe_notional_0p40_v1"

BASELINE_EXPERIMENT_ID = "exp-20260531-016"
BASELINE_NOTIONAL_USD = 10_000.0
SAFE_NOTIONAL_USD = 4_000.0
SAFE_NOTIONAL_SCALAR = SAFE_NOTIONAL_USD / BASELINE_NOTIONAL_USD

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_021_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _patch_framework() -> None:
    source._patch_framework()
    for module in (source, source.source, framework):
        module.EXPERIMENT_ID = EXPERIMENT_ID
        module.STEM = STEM
        module.TRIAL_FAMILY = TRIAL_FAMILY
        module.CHANGED_VARIABLE = CHANGED_VARIABLE
        module.RULE_VERSION = RULE_VERSION
        module.OUT_DIR = OUT_DIR
        module.OUT_JSON = OUT_JSON
        module.BEFORE_AGG_JSON = BEFORE_AGG_JSON
        module.AFTER_AGG_JSON = AFTER_AGG_JSON
        module.LOG_JSON = LOG_JSON
        module.TICKET_JSON = TICKET_JSON
        module.CARD_MD = CARD_MD
        module.ARTIFACT_MD = ARTIFACT_MD
        module.EXPERIMENT_LOG = EXPERIMENT_LOG

    framework.base.BASE_NOTIONAL_USD = SAFE_NOTIONAL_USD
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, audit = source._candidate_rows_for_window(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    safe_candidates: list[dict[str, Any]] = []
    for row in candidates:
        safe_candidates.append(
            {
                **row,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "safe_notional_rule_version": RULE_VERSION,
                "paper_notional_policy": "fixed_0p40x_exp016_budget",
                "baseline_paper_notional_usd": BASELINE_NOTIONAL_USD,
                "safe_paper_notional_usd": SAFE_NOTIONAL_USD,
                "safe_notional_scalar": SAFE_NOTIONAL_SCALAR,
            }
        )
    return safe_candidates, {
        **audit,
        "rule_version": RULE_VERSION,
        "source_rule_version": source.RULE_VERSION,
        "source_experiment_id": BASELINE_EXPERIMENT_ID,
        "safe_notional_scalar": SAFE_NOTIONAL_SCALAR,
        "baseline_paper_notional_usd": BASELINE_NOTIONAL_USD,
        "safe_paper_notional_usd": SAFE_NOTIONAL_USD,
    }


def _prior_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    current = payload["delta_metrics"]["aggregate"]
    current_target = payload.get("target_trade_summary") or {}
    prior = source._load_prior_result(
        BASELINE_EXPERIMENT_ID,
        "exp_20260531_016_full_universe_alpha_score_market_regime_candidate_pool.json",
    )
    out = source._prior_comparison(payload)
    if prior:
        agg = (prior.get("delta_metrics") or {}).get("aggregate") or {}
        target = prior.get("target_trade_summary") or {}
        out["exp016_market_regime_10k"] = {
            "experiment_id": BASELINE_EXPERIMENT_ID,
            "decision": prior.get("decision"),
            "ev_delta_sum": agg.get("expected_value_score_delta_sum"),
            "pnl_delta_sum": agg.get("total_pnl_delta_sum"),
            "max_drawdown_delta_max": agg.get("max_drawdown_delta_max"),
            "target_trades": target.get("total_trade_count"),
            "max_single_positive_share": target.get("max_single_positive_pnl_share"),
            "positive_hhi": target.get("positive_pnl_hhi"),
        }
    out["current_safe_notional_0p40"] = {
        "ev_delta_sum": current.get("expected_value_score_delta_sum"),
        "pnl_delta_sum": current.get("total_pnl_delta_sum"),
        "max_drawdown_delta_max": current.get("max_drawdown_delta_max"),
        "target_trades": current_target.get("total_trade_count"),
        "max_single_positive_share": current_target.get("max_single_positive_pnl_share"),
        "positive_hhi": current_target.get("positive_pnl_hhi"),
    }
    return out


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = source._postprocess_payload(payload)
    gate4 = payload["gate4"]
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if gate4["passed"]
        else "rejected_full_universe_alpha_score_market_regime_safe_notional"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "The exp-20260531-016 alpha_score market-regime candidate source "
                "may be promotable as a default-off paper sleeve if the paper "
                "risk budget is pre-registered lower, preserving broad EV while "
                "keeping max drawdown drift inside Gate 4."
            ),
            "change_type": "default_off_paper_risk_allocation",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 8,
            "nearby_prior_experiments": [
                "exp-20260531-005",
                "exp-20260531-007",
                "exp-20260531-008",
                "exp-20260531-009",
                "exp-20260531-011",
                "exp-20260531-014",
                "exp-20260531-016",
                "exp-20260531-017",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "pre_registered_default_off_notional_risk_budget",
            "prediction": {
                "success_probability": 0.42,
                "expected_ev_delta": 1.5,
                "expected_pnl_delta": 30000.0,
                "main_failure_modes": [
                    "drawdown_drift_still_high",
                    "ev_too_diluted",
                    "window_regression",
                    "not_promotable_without_shared_adapter",
                ],
                "confidence_reason": (
                    "Exp016 improved all windows and passed concentration but "
                    "missed drawdown by sizing. A 0.40x pre-registered notional "
                    "budget should preserve positive EV while reducing drawdown "
                    "drift."
                ),
                "recorded_at": "2026-05-31T16:36:48+00:00",
                "brier_score": round((0.42 - actual_success) ** 2, 6),
            },
            "parameters": {
                **payload["parameters"],
                "source_definition_fixed_from": BASELINE_EXPERIMENT_ID,
                "baseline_paper_notional_usd": BASELINE_NOTIONAL_USD,
                "safe_paper_notional_usd": SAFE_NOTIONAL_USD,
                "safe_notional_scalar": SAFE_NOTIONAL_SCALAR,
                "changed_only": [
                    "keep the exp-20260531-016 top-decile alpha_score candidate source fixed",
                    "keep the exp-20260531-016 SPY 50d MA and IWM-vs-SPY 20d market gate fixed",
                    "keep top-1/day routing, 20-trading-day hold, score weights, core logic, LLM/news, and live orders fixed",
                    "change only default-off paper notional from $10,000 to $4,000 per candidate",
                ],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "risk allocation / candidate_pool: exp016's alpha source "
                    "has broad positive EV but too much overlay drawdown; a "
                    "smaller fixed paper budget may make it activation-ready."
                ),
                "2_history_check": {
                    "exp-20260531-016": (
                        "The same candidate source improved all windows and "
                        "passed concentration, but failed Gate 4 because "
                        "late_strong max drawdown drift was +1.06pp versus "
                        "the +0.50pp guardrail."
                    ),
                    "exp-20260531-017": (
                        "Component attribution did not provide a clean monotonic "
                        "ladder, so this run avoids another component threshold "
                        "and tests only a pre-registered risk budget."
                    ),
                    "alpha_playbook": (
                        "Raw alpha_score top-N and state-gate mining remain "
                        "unsafe. This run is a safety-budget test for the one "
                        "market-gated lead that already passed concentration."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate "
                    "EV/PnL; 3/3 EV-improved windows; no PnL-regressed window; "
                    ">=20 paper trades across all 3 windows; drawdown drift "
                    "<=0.5pp; survival >=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional.py"
                ),
            },
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "shared_adapter_added": False,
                "parity_note": (
                    "No production code path is changed. A positive replay lead "
                    "must still be promoted through a shared default-off adapter "
                    "that computes the same PIT alpha_score surface, market gate, "
                    "and $4,000 paper notional in production and replay."
                ),
            },
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "trade_enabled": False,
                "promotion_requirement": (
                    "If Gate 4 passes, the next step is a shared default-off "
                    "paper adapter plus production/replay parity tests before "
                    "any activation review. Live/default orders remain disabled."
                ),
            },
            "why_not_other_changes": (
                "The user asked to push the exp016 lead toward上线. I did not "
                "add a new alpha_score threshold, component gate, ticker "
                "exception, or exit rule because those would increase "
                "multiple-testing risk. The one failure was drawdown from fixed "
                "$10k overlay sizing, so this run tests only the smaller "
                "default-off paper budget."
            ),
            "prior_candidate_pool_comparison": _prior_comparison(payload),
            "interpretation": (
                "The safe-notional market-regime alpha_score source cleared "
                "Gate 4 as a replay-only lead. It is not live or production "
                "enabled until a shared default-off adapter and parity tests "
                "are added."
                if gate4["passed"]
                else (
                    "The safe-notional market-regime alpha_score source did "
                    "not clear Gate 4. Do not promote it or keep reducing "
                    "notional on the same frozen windows without forward "
                    "replacement-value rows."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "A shared production/replay default-off adapter for the alpha_score "
                "market-regime source, parity tests, and forward replacement-value "
                "rows. No live/default orders before that adapter exists."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "The alpha_score surface and market gate are rebuilt point-in-time using "
        "signal-date OHLCV/context, matching exp016. The only changed variable "
        "versus exp016 is fixed default-off paper notional: $4,000 instead of "
        "$10,000. Paper entry is the next available open with production entry "
        "slippage; exit is 20 trading days after the signal with target-side "
        "sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["target_trade_field_coverage"] = framework._field_coverage(
        all_target_trades,
        [
            "ticker",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "paper_notional_usd",
            "known_at",
            "alpha_score",
            "alpha_score_bucket",
            "alpha_score_rank_pct",
            "alpha_score_components",
            "rank_score_validity_regime_bucket",
            "spy_above_50d_ma",
            "iwm_minus_spy_ret20",
            "safe_notional_scalar",
        ],
    )
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
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
    comparison = payload.get("prior_candidate_pool_comparison") or {}
    return "\n".join(
        [
            "# exp-20260531-021 Full-Universe Alpha-Score Market-Regime Safe Notional",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: keep the exp-20260531-016 candidate source and market gate fixed, but reduce fixed paper notional from $10,000 to $4,000 per candidate.",
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
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Prior Alpha-Score Variants",
            "",
            "```json",
            json.dumps(comparison, indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result still requires a shared default-off adapter and parity tests before activation.",
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
        "title": "Full-universe alpha-score market-regime safe notional",
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
        },
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    report = _build_report(payload)
    framework.base._write_text(CARD_MD, report)
    framework.base._write_text(ARTIFACT_MD, report)
    framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _patch_framework()
    payload = _postprocess_payload(framework._build_payload())
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
                    "target_trade_summary": payload["target_trade_summary"],
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
