"""exp-20260605-015: Promote peer-confirmed Companyfacts alpha to shared adapter.

This alpha search attempts to promote exp-20260605-014's positive broad
Companyfacts peer-confirmed filing-drift replay lead into a production-realistic
default-off paper adapter. The backtest measurement uses the same shared module
that a daily paper sleeve would use, so the after result does not depend on a
private experiment-only candidate implementation.

No live order path, core ranking, sizing, exits, LLM/news path, or watchlist is
changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from companyfacts_peer_confirmed_filing_drift_paper_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_companyfacts_peer_confirmed_historical_trades,
    load_companyfacts_growth_rows,
)
import exp_20260605_011_broad_companyfacts_dual_growth_rs_candidate_pool as base  # noqa: E402


EXP_ID = "exp-20260605-015"
STEM = "broad_companyfacts_peer_confirmed_adapter"
TRIAL_FAMILY = "broad_companyfacts_peer_confirmed_filing_drift_adapter"
TRIAL_VARIANT_ID = "broad_companyfacts_peer_confirmed_shared_adapter_v1"
CHANGED_VARIABLE = RULE_VERSION

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260605_015_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

MAX_DRAWDOWN_WORSE = 0.005
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "shared_adapter_candidate_not_promoted",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": False,
    "parity_test_added": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "The production-realistic replay calls "
        "quant/companyfacts_peer_confirmed_filing_drift_paper_sleeve.py, but the "
        "candidate adapter is not wired into quant/run.py, daily reports, "
        "watchlists, or order surfaces because Gate 4 failed."
    ),
}


def _patch_base_module() -> None:
    base.EXP_ID = EXP_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.BEFORE_JSON = BEFORE_JSON
    base.AFTER_JSON = AFTER_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.ARTIFACT_MD = ARTIFACT_MD
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PAPER_NOTIONAL = float(DEFAULT_CONFIG["paper_notional_usd"])
    base.HOLD_DAYS = int(DEFAULT_CONFIG["hold_days"])
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI


def _gate4(
    aggregate_comparison: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    gate4 = base._gate4(aggregate_comparison, results, target_summary)
    if gate4["passed"]:
        gate4["decision"] = "accepted_default_off_broad_companyfacts_peer_confirmed_adapter"
    else:
        gate4["decision"] = "rejected_default_off_broad_companyfacts_peer_confirmed_adapter"
    gate4["requires_parity_before_promotion"] = True
    gate4["parity_test_added"] = True
    gate4["shared_adapter_module"] = "quant/companyfacts_peer_confirmed_filing_drift_paper_sleeve.py"
    gate4["promotion_allowed"] = bool(gate4["passed"])
    gate4["production_parity_note"] = PRODUCTION_IMPACT["parity_note"]
    return gate4


def _compare_window(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score_delta": round(
            float(after.get("expected_value_score") or 0.0)
            - float(before.get("expected_value_score") or 0.0),
            4,
        ),
        "strategy_total_pnl_delta": round(
            float(after.get("total_pnl") or 0.0)
            - float(before.get("total_pnl") or 0.0),
            2,
        ),
        "max_drawdown_delta": round(
            float(after.get("max_drawdown_pct") or 0.0)
            - float(before.get("max_drawdown_pct") or 0.0),
            6,
        ),
    }


def _judge_compatible_aggregate(metrics: dict[str, Any]) -> dict[str, Any]:
    payload = dict(metrics)
    payload["total_pnl"] = metrics.get("strategy_total_pnl")
    payload["max_drawdown_pct"] = metrics.get("max_drawdown_pct_max")
    payload["survival_rate"] = metrics.get("min_survival_rate")
    payload["total_trades"] = metrics.get("trade_count")
    return payload


def build_payload() -> dict[str, Any]:
    _patch_base_module()
    base._configure_overlay_module()
    completed_at = base._utc_now()
    universe = base.get_universe()
    frames = base.load_warehouse_frames()
    prices = base._price_map_from_frames(frames)
    growth_rows, growth_source = load_companyfacts_growth_rows(path=base.GROWTH_PATH)
    candidates, candidate_audit = build_companyfacts_peer_confirmed_historical_trades(
        ohlcv_by_ticker=frames,
        companyfacts_growth_rows=growth_rows,
        windows=base.WINDOWS,
        config=DEFAULT_CONFIG,
    )

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    for label, window in base.WINDOWS.items():
        result = base.BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        selected = [
            trade
            for trade in candidates
            if trade.get("window") == label
            and window["start"] <= str(trade.get("signal_date")) <= window["end"]
        ]
        event_curve = base.overlay._event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before = base.overlay._core_metrics(result)
        after = base.overlay._combined_metrics(result, event_curve, selected)
        before_metrics[label] = before
        after_metrics[label] = after
        results.append(
            {
                "label": label,
                "window": window,
                "before": before,
                "after": after,
                "comparison": _compare_window(before, after),
                "target_trade_count": len(selected),
                "target_trade_pnl_usd": round(
                    sum(float(trade.get("pnl") or 0.0) for trade in selected),
                    2,
                ),
                "selected_trades": selected,
            }
        )

    aggregate_before = base._aggregate_metrics(before_metrics)
    aggregate_after = base._aggregate_metrics(after_metrics)
    aggregate_comparison = base._compare_aggregate(aggregate_before, aggregate_after)
    target_summary = base._target_summary(candidates)
    gate4 = _gate4(aggregate_comparison, results, target_summary)

    return {
        "experiment_id": EXP_ID,
        "completed_at": completed_at,
        "anti_js": "No JavaScript was used.",
        "lane": "alpha_search",
        "preflight": {
            "alpha_hypothesis": (
                "Promoting the positive broad Companyfacts peer-confirmed "
                "filing-drift lead into a shared default-off adapter preserves "
                "the three-window replacement-value edge while making forward "
                "production paper evidence auditable."
            ),
            "category": "entry_candidate_pool",
            "nearby_prior_experiments": [
                "exp-20260605-014",
                "exp-20260605-011",
                "exp-20260605-007",
            ],
            "single_causal_variable": CHANGED_VARIABLE,
            "success_standard": (
                "Canonical three-window before/after aggregate EV and PnL must "
                "match the positive lead direction, no window EV/PnL regression, "
                f"max drawdown drift <= {MAX_DRAWDOWN_WORSE}, target trades >= "
                f"{MIN_TARGET_TRADES}, all three windows represented, and the "
                "daily adapter must be default-off with no live order impact."
            ),
            "reproducible_if_failed": True,
        },
        "parameters": {
            "paper_notional": DEFAULT_CONFIG["paper_notional_usd"],
            "hold_days": DEFAULT_CONFIG["hold_days"],
            "max_fundamental_age_days": DEFAULT_CONFIG["max_fundamental_age_days"],
            "peer_confirmation_lookback_days": DEFAULT_CONFIG[
                "peer_confirmation_lookback_days"
            ],
            "min_peer_confirmations": DEFAULT_CONFIG["min_peer_confirmations"],
            "min_revenue_yoy_growth": DEFAULT_CONFIG["min_revenue_yoy_growth"],
            "min_profit_yoy_growth": DEFAULT_CONFIG["min_profit_yoy_growth"],
            "min_price": DEFAULT_CONFIG["min_price"],
            "min_avg_dollar_volume_20d": DEFAULT_CONFIG["min_avg_dollar_volume_20d"],
            "min_ret20_excess_spy": DEFAULT_CONFIG["min_ret20_excess_spy"],
            "min_close_location": DEFAULT_CONFIG["min_close_location"],
            "min_volume_ratio_20d": DEFAULT_CONFIG["min_volume_ratio_20d"],
            "same_ticker_cooldown_days": DEFAULT_CONFIG["same_ticker_cooldown_days"],
            "daily_selection": "top_1_by_shared_peer_confirmed_growth_drift_score",
            "source_rule_version": SOURCE_RULE_VERSION,
            "shared_adapter_rule_version": RULE_VERSION,
            "trade_enabled": False,
        },
        "source_data": {
            "growth_path": growth_source,
            "warehouse": "data/experiments/exp-20260519-030/warehouse_main.sqlite",
            "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
        },
        "gate2": base._position_field_check(),
        "gate3": {
            "survival_rate_unchanged": True,
            "min_survival_rate": aggregate_before["min_survival_rate"],
            "note": "Default-off paper adapter does not alter core signal filters.",
        },
        "candidate_audit": candidate_audit,
        "target_summary": target_summary,
        "results": results,
        "aggregate": {
            "before": aggregate_before,
            "after": aggregate_after,
            "comparison": aggregate_comparison,
        },
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "prediction": (base._load_json(TICKET_JSON, {}).get("prediction") or {}),
        "next_retry_requires": [
            "collect forward paper replacement-value rows from the shared adapter",
            "do not retune Companyfacts peer thresholds/lookbacks/cooldowns on the frozen sample",
            "consider only new free-data relationship evidence if this family is revisited",
        ],
        "related_files": [
            base._repo_rel(Path(__file__)),
            "quant/companyfacts_peer_confirmed_filing_drift_paper_sleeve.py",
            "quant/test_companyfacts_peer_confirmed_filing_drift_paper_sleeve.py",
            base._repo_rel(OUT_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(ARTIFACT_MD),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(base.GROWTH_PATH),
            "data/reference/broad_market_sector_map.json",
        ],
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    prediction = payload.get("prediction") or {}
    return {
        "experiment_id": EXP_ID,
        "timestamp": payload["completed_at"],
        "status": payload["gate4"]["status"],
        "lane": "alpha_search",
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": (
            "Promoted the broad Companyfacts peer-confirmed filing-drift "
            "candidate-pool alpha into a shared default-off paper adapter and "
            "retested it through the canonical three-window replay."
        ),
        "change_type": "default_off_paper_adapter",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260605-014",
            "exp-20260605-011",
            "exp-20260605-007",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "positive_replay_lead_shared_adapter_promotion",
        "component": base._repo_rel(Path(__file__)),
        "parameters": payload["parameters"],
        "before_metrics": payload["aggregate"]["before"],
        "after_metrics": payload["aggregate"]["after"],
        "delta_metrics": comparison,
        "production_impact": PRODUCTION_IMPACT,
        "decision": payload["gate4"]["decision"],
        "rejection_reason": ";".join(payload["gate4"]["failed_reasons"])
        if payload["gate4"]["failed_reasons"]
        else None,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "prediction": {
            **prediction,
            "actual_success": actual_success,
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "brier_score": round(
                (float(prediction.get("success_probability") or 0.0) - actual_success) ** 2,
                6,
            ),
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "anti_js": "No JavaScript was used.",
    }


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} Broad Companyfacts Peer-Confirmed Adapter",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Hypothesis",
        "",
        payload["preflight"]["alpha_hypothesis"],
        "",
        "## Gate 1-4",
        "",
        base._window_table(payload["results"]),
        "",
        "## Candidate Audit",
        "",
        "```json",
        json.dumps(payload["candidate_audit"], indent=2, sort_keys=True),
        "```",
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Failure Diagnosis",
            "",
            (
                "The positive exp-20260605-014 lead was not promoted because the "
                "production-realistic shared helper applies same-ticker cooldowns "
                "chronologically. The earlier replay iterated canonical windows in "
                "reverse chronology, so later-window selections could suppress "
                "older-window candidates; production cannot reproduce that behavior. "
                "With chronological cooldown semantics, old_thin regressed and "
                "drawdown drift exceeded the guard."
            ),
            "",
            "## Gate 4",
            "",
        ]
    for key, value in payload["gate4"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260605_015_broad_companyfacts_peer_confirmed_adapter.py"
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _patch_base_module()
    payload = build_payload()
    log_record = _experiment_log_record(payload)
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, log_record)
    base._write_json(BEFORE_JSON, _judge_compatible_aggregate(payload["aggregate"]["before"]))
    base._write_json(AFTER_JSON, _judge_compatible_aggregate(payload["aggregate"]["after"]))
    _write_artifact(payload)
    base._update_ticket(payload)
    base._update_registry(payload)
    base._append_experiment_log(log_record)
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": {
                    "target_trade_count": payload["target_summary"]["target_trade_count"],
                    "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
                    "max_single_positive_share": payload["target_summary"][
                        "max_single_positive_share"
                    ],
                    "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
                },
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
