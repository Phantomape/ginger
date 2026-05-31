"""exp-20260531-024: alpha-score source-consensus support.

This alpha search keeps the accepted exp-20260531-021 alpha-score market-regime
candidate definition fixed. The single changed variable is a small default-off
paper notional support when the same ticker and signal date also appear in an
accepted free-data paper source: FINRA/IWM or VBB.

Core signal generation, alpha-score weights, market gates, hold days, live
watchlists, order paths, LLM/news behavior, and production trading are
unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional as base_exp


framework = base_exp.framework
REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260531-024"
STEM = "alpha_score_source_consensus_support"
TRIAL_FAMILY = "alpha_score_market_regime_source_consensus_support"
CHANGED_VARIABLE = "alpha_score_source_consensus_support_scalar_v1"
RULE_VERSION = "alpha_score_market_regime_source_consensus_support_1p25_v1"

BASELINE_EXPERIMENT_ID = "exp-20260531-021"
BASELINE_SAFE_NOTIONAL_USD = 4_000.0
CONSENSUS_NOTIONAL_SCALAR = 1.25
CONSENSUS_NOTIONAL_USD = BASELINE_SAFE_NOTIONAL_USD * CONSENSUS_NOTIONAL_SCALAR

CONSENSUS_SOURCE_FILES = {
    "FINRA_IWM_CONFIRMED_PAPER": (
        "data/experiments/exp-20260530-007/"
        "exp_20260530_007_finra_iwm_same_ticker_cooldown_candidate_pool.json"
    ),
    "VOLUME_BREADTH_BREAKOUT_PAPER": (
        "data/experiments/exp-20260529-004/"
        "exp_20260529_004_vbb_cost_liquidity_support.json"
    ),
}

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_024_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

_ORIGINAL_PAPER_TRADE_FROM_CANDIDATE = None


def _signal_key(row: dict[str, Any]) -> tuple[str, str] | None:
    date_value = str(row.get("signal_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    if not date_value or not ticker:
        return None
    return date_value, ticker


def _load_consensus_keys() -> dict[tuple[str, str], set[str]]:
    keys: dict[tuple[str, str], set[str]] = {}
    for source_name, rel_path in CONSENSUS_SOURCE_FILES.items():
        path = REPO_ROOT / rel_path
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for rows in (payload.get("target_trades_by_window") or {}).values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                key = _signal_key(row)
                if key is None:
                    continue
                keys.setdefault(key, set()).add(source_name)
    return keys


def _patch_framework() -> None:
    global _ORIGINAL_PAPER_TRADE_FROM_CANDIDATE
    base_exp._patch_framework()
    for module in (base_exp, base_exp.source, base_exp.source.source, framework):
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

    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report
    _ORIGINAL_PAPER_TRADE_FROM_CANDIDATE = framework.base._paper_trade_from_candidate
    framework.base._paper_trade_from_candidate = _paper_trade_from_candidate


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, audit = base_exp._candidate_rows_for_window(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    consensus = _load_consensus_keys()
    enriched: list[dict[str, Any]] = []
    consensus_count = 0
    consensus_source_counts: dict[str, int] = {}
    for row in candidates:
        key = _signal_key(row)
        sources = sorted(consensus.get(key, set())) if key else []
        has_consensus = bool(sources)
        if has_consensus:
            consensus_count += 1
            for source_name in sources:
                consensus_source_counts[source_name] = (
                    consensus_source_counts.get(source_name, 0) + 1
                )
        enriched.append(
            {
                **row,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "source_consensus_rule_version": RULE_VERSION,
                "source_consensus_support_applied": has_consensus,
                "source_consensus_sources": sources,
                "source_consensus_known_at": (
                    "after_signal_date_close_before_next_open_paper_entry"
                ),
                "baseline_safe_paper_notional_usd": BASELINE_SAFE_NOTIONAL_USD,
                "source_consensus_notional_scalar": (
                    CONSENSUS_NOTIONAL_SCALAR if has_consensus else 1.0
                ),
                "source_consensus_paper_notional_usd": (
                    CONSENSUS_NOTIONAL_USD if has_consensus else BASELINE_SAFE_NOTIONAL_USD
                ),
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    return enriched, {
        **audit,
        "rule_version": RULE_VERSION,
        "source_experiment_id": BASELINE_EXPERIMENT_ID,
        "source_consensus_key_count": len(consensus),
        "source_consensus_candidate_count": consensus_count,
        "source_consensus_source_counts": dict(sorted(consensus_source_counts.items())),
        "source_consensus_notional_scalar": CONSENSUS_NOTIONAL_SCALAR,
        "baseline_safe_paper_notional_usd": BASELINE_SAFE_NOTIONAL_USD,
        "source_consensus_paper_notional_usd": CONSENSUS_NOTIONAL_USD,
        "consensus_source_files": CONSENSUS_SOURCE_FILES,
    }


def _paper_trade_from_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    if _ORIGINAL_PAPER_TRADE_FROM_CANDIDATE is None:
        raise RuntimeError("paper trade hook was not initialized")
    trade = _ORIGINAL_PAPER_TRADE_FROM_CANDIDATE(snapshot, candidate)
    if trade is None:
        return None
    notional = (
        CONSENSUS_NOTIONAL_USD
        if candidate.get("source_consensus_support_applied")
        else BASELINE_SAFE_NOTIONAL_USD
    )
    pnl_pct = float(trade.get("pnl_pct_net") or 0.0)
    trade.update(
        {
            "paper_notional_usd": framework.base._round(notional, 2),
            "pnl": framework.base._round(notional * pnl_pct, 2),
            "source_consensus_rule_version": RULE_VERSION,
            "source_consensus_support_applied": bool(
                candidate.get("source_consensus_support_applied")
            ),
            "source_consensus_sources": list(
                candidate.get("source_consensus_sources") or []
            ),
            "source_consensus_notional_scalar": (
                CONSENSUS_NOTIONAL_SCALAR
                if candidate.get("source_consensus_support_applied")
                else 1.0
            ),
            "baseline_safe_paper_notional_usd": BASELINE_SAFE_NOTIONAL_USD,
            "source_consensus_paper_notional_usd": framework.base._round(notional, 2),
        }
    )
    return trade


def _source_consensus_summary(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [
        trade
        for trades in payload.get("target_trades_by_window", {}).values()
        for trade in trades
        if trade.get("source_consensus_support_applied")
    ]
    by_window: dict[str, dict[str, Any]] = {}
    for label, trades in payload.get("target_trades_by_window", {}).items():
        window_rows = [
            trade for trade in trades if trade.get("source_consensus_support_applied")
        ]
        by_window[label] = {
            "trade_count": len(window_rows),
            "supported_pnl": framework.base._round(
                sum(float(row.get("pnl") or 0.0) for row in window_rows),
                2,
            ),
            "incremental_support_pnl": framework.base._round(
                sum(
                    float(row.get("pnl") or 0.0)
                    * ((CONSENSUS_NOTIONAL_SCALAR - 1.0) / CONSENSUS_NOTIONAL_SCALAR)
                    for row in window_rows
                ),
                2,
            ),
        }
    return {
        "supported_trade_count": len(rows),
        "supported_windows": [
            label for label, row in by_window.items() if row["trade_count"] > 0
        ],
        "supported_total_pnl": framework.base._round(
            sum(float(row.get("pnl") or 0.0) for row in rows),
            2,
        ),
        "incremental_support_pnl": framework.base._round(
            sum(
                float(row.get("pnl") or 0.0)
                * ((CONSENSUS_NOTIONAL_SCALAR - 1.0) / CONSENSUS_NOTIONAL_SCALAR)
                for row in rows
            ),
            2,
        ),
        "by_window": by_window,
        "source_counts": dict(
            sorted(
                {
                    source_name: sum(
                        1
                        for row in rows
                        if source_name in (row.get("source_consensus_sources") or [])
                    )
                    for source_name in CONSENSUS_SOURCE_FILES
                }.items()
            )
        ),
    }


def _accepted_baseline_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    baseline_path = (
        REPO_ROOT
        / "data/experiments/exp-20260531-021/"
        / "exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional.json"
    )
    if not baseline_path.exists():
        return {"available": False, "reason": "missing_exp_20260531_021_artifact"}
    with baseline_path.open("r", encoding="utf-8") as handle:
        baseline = json.load(handle)
    current_after = payload["delta_metrics"]["aggregate"]
    baseline_after = (baseline.get("delta_metrics") or {}).get("aggregate") or {}
    by_window: dict[str, dict[str, Any]] = {}
    for label in framework.base.WINDOWS:
        cur = payload["after_metrics"][label]
        prev = baseline["after_metrics"][label]
        by_window[label] = {
            "expected_value_score_delta": framework.base._round(
                cur["expected_value_score"] - prev["expected_value_score"],
                4,
            ),
            "total_pnl_delta": framework.base._round(
                cur["total_pnl"] - prev["total_pnl"],
                2,
            ),
            "max_drawdown_delta": framework.base._round(
                cur["max_drawdown_pct"] - prev["max_drawdown_pct"],
                4,
            ),
        }
    return {
        "available": True,
        "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
        "baseline_artifact": framework.base._repo_rel(baseline_path),
        "baseline_after_aggregate": {
            "expected_value_score_sum": baseline_after.get("after_expected_value_score_sum"),
            "total_pnl_sum": baseline_after.get("after_total_pnl_sum"),
            "max_drawdown_delta_max": baseline_after.get("max_drawdown_delta_max"),
        },
        "current_after_aggregate": {
            "expected_value_score_sum": current_after.get("after_expected_value_score_sum"),
            "total_pnl_sum": current_after.get("after_total_pnl_sum"),
            "max_drawdown_delta_max": current_after.get("max_drawdown_delta_max"),
        },
        "incremental_vs_exp021": by_window,
        "windows_ev_regressed_vs_exp021": sum(
            1 for row in by_window.values() if row["expected_value_score_delta"] < 0
        ),
        "windows_pnl_regressed_vs_exp021": sum(
            1 for row in by_window.values() if row["total_pnl_delta"] < 0
        ),
        "aggregate_expected_value_score_delta_vs_exp021": framework.base._round(
            float(current_after.get("after_expected_value_score_sum") or 0.0)
            - float(baseline_after.get("after_expected_value_score_sum") or 0.0),
            4,
        ),
        "aggregate_total_pnl_delta_vs_exp021": framework.base._round(
            float(current_after.get("after_total_pnl_sum") or 0.0)
            - float(baseline_after.get("after_total_pnl_sum") or 0.0),
            2,
        ),
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = base_exp._postprocess_payload(payload)
    gate4 = payload["gate4"]
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_source_consensus_adapter"
        if gate4["passed"]
        else "rejected_alpha_score_source_consensus_support"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    source_summary = _source_consensus_summary(payload)
    accepted_comparison = _accepted_baseline_comparison(payload)
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Accepted alpha_score market-regime paper candidates may deserve "
                "a small default-off notional support only when another accepted "
                "free-data paper source selects the same ticker on the same "
                "signal date."
            ),
            "change_type": "default_off_paper_allocation",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "default_off_paper_allocation",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260531-021",
                "exp-20260531-023",
                "exp-20260530-007",
                "exp-20260529-004",
                "exp-20260526-014",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "production_visible_cross_source_agreement_field",
            "prediction": {
                "success_probability": 0.31,
                "expected_ev_delta": None,
                "expected_pnl_delta": None,
                "main_failure_modes": [
                    "consensus_sample_too_thin",
                    "window_regression",
                    "drawdown_drift",
                    "nearby_alpha_score_multiple_testing",
                ],
                "confidence_reason": (
                    "The accepted alpha_score adapter is production-visible and "
                    "source consensus is a distinct cross-sleeve agreement field. "
                    "A pre-run artifact spot check showed consensus trades were "
                    "positive in all three windows, but the sample could still be "
                    "too thin for a retained adapter increment."
                ),
                "recorded_at": "2026-05-31T19:09:32+00:00",
                "brier_score": round((0.31 - actual_success) ** 2, 6),
            },
            "parameters": {
                **payload["parameters"],
                "source_definition_fixed_from": BASELINE_EXPERIMENT_ID,
                "baseline_safe_paper_notional_usd": BASELINE_SAFE_NOTIONAL_USD,
                "source_consensus_notional_scalar": CONSENSUS_NOTIONAL_SCALAR,
                "source_consensus_paper_notional_usd": CONSENSUS_NOTIONAL_USD,
                "consensus_source_files": CONSENSUS_SOURCE_FILES,
                "changed_only": [
                    "keep exp-20260531-021 alpha_score candidate source fixed",
                    "keep market gate, top-1/day, 20-trading-day hold, score weights, core logic, LLM/news, and live orders fixed",
                    "apply 1.25x paper notional only when the alpha_score candidate also appears in an accepted FINRA/IWM or VBB paper source on the same signal date",
                ],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "capital allocation / candidate_pool: cross-source agreement "
                    "between the accepted alpha_score market-regime sleeve and "
                    "other accepted free-data sleeves should identify higher "
                    "confidence default-off paper candidates."
                ),
                "2_history_check": {
                    "exp-20260531-021": (
                        "Accepted the fixed alpha_score market-regime source at "
                        "$4,000 notional with +1.6439 aggregate EV and no "
                        "drawdown worsening."
                    ),
                    "exp-20260531-023": (
                        "Promoted that route into a shared default-off adapter. "
                        "This run does not alter the adapter or live/default orders."
                    ),
                    "exp-20260530-007": (
                        "Accepted FINRA/IWM/cooldown source as a default-off "
                        "paper candidate pool."
                    ),
                    "exp-20260529-004": (
                        "Accepted VBB cost/liquidity support in the default-off "
                        "VBB paper route."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate "
                    "EV/PnL; no EV or PnL-regressed window versus core; no "
                    "regression versus accepted exp-20260531-021; >=20 supported "
                    "trades across all 3 windows; drawdown drift <=0.5pp; "
                    "survival >=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260531_024_alpha_score_source_consensus_support.py"
                ),
            },
            "source_consensus_summary": source_summary,
            "accepted_baseline_comparison": accepted_comparison,
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_ranking": False,
                "alters_core_sizing": False,
                "alters_core_exits": False,
                "llm_or_news_changed": False,
                "shared_adapter_changed": False,
                "trade_enabled": False,
                "default_off_paper_only": True,
                "replay_only": True,
                "promotion_requirement": (
                    "A positive result still needs a separate shared adapter "
                    "change that computes the same source-consensus field in "
                    "production before it can be retained."
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
            },
            "why_not_other_changes": (
                "Skipped alpha_score score-weight, top-N, market-gate, hold-day, "
                "and base-notional retunes because the playbook freezes nearby "
                "alpha_score mining. This run tests only a distinct "
                "cross-source agreement field using accepted free-data sleeves."
            ),
            "interpretation": (
                "The source-consensus support cleared the replay Gate 4, but it "
                "is not promoted because no shared production adapter computes "
                "the source-consensus support field yet."
                if gate4["passed"]
                else (
                    "The source-consensus support did not clear Gate 4. Do not "
                    "promote it or retry nearby source-consensus scalars on the "
                    "same frozen windows without forward replacement-value rows."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If positive, add a shared default-off source-consensus adapter "
                "and collect forward replacement-value rows. If rejected, do not "
                "retune the scalar on these frozen windows."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    if (
        accepted_comparison.get("available")
        and (
            accepted_comparison["windows_ev_regressed_vs_exp021"] > 0
            or accepted_comparison["windows_pnl_regressed_vs_exp021"] > 0
            or accepted_comparison["aggregate_expected_value_score_delta_vs_exp021"] <= 0
        )
    ):
        payload["decision"] = "rejected_alpha_score_source_consensus_support"
        payload["status"] = payload["decision"]
        payload["rejection_reason"] = (
            "Failed incremental comparison versus accepted exp-20260531-021."
        )
        payload["interpretation"] = (
            "The source-consensus support failed the required comparison against "
            "the accepted alpha_score adapter baseline."
        )
    payload["backtest_protocol"]["execution_model"] = (
        "The accepted exp-20260531-021 alpha_score market-regime source is "
        "rebuilt point-in-time using signal-date OHLCV/context. The only "
        "changed variable is a 1.25x paper-notional support for candidates that "
        "also appear in accepted FINRA/IWM or VBB paper sources on the same "
        "signal date. Paper entry remains next open and exit remains 20 trading "
        "days after the signal."
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
            "rank_score_validity_regime_bucket",
            "source_consensus_support_applied",
            "source_consensus_sources",
            "source_consensus_notional_scalar",
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
    gate4 = payload["gate4"]
    accepted_comparison = payload.get("accepted_baseline_comparison") or {}
    return "\n".join(
        [
            "# exp-20260531-024 Alpha-Score Source-Consensus Support",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: apply `1.25x` paper notional only to accepted alpha_score market-regime candidates that overlap accepted FINRA/IWM or VBB paper sources on the same signal date.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta vs core: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta vs core: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- supported trades: `{consensus['supported_trade_count']}` across `{len(consensus['supported_windows'])}` windows",
            f"- incremental support PnL: `${consensus['incremental_support_pnl']}`",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Comparison Versus Accepted exp-20260531-021",
            "",
            "```json",
            json.dumps(accepted_comparison, indent=2, sort_keys=True),
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
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed.",
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
        "title": "Alpha-score source-consensus support",
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
                    "source_consensus_summary": payload["source_consensus_summary"],
                    "accepted_baseline_comparison": payload[
                        "accepted_baseline_comparison"
                    ],
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
