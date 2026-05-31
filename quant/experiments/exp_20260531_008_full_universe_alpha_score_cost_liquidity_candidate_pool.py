"""exp-20260531-008: full-universe alpha-score cost/liquidity pool.

This alpha search keeps the rejected exp-20260531-005 full-universe
``alpha_score`` top-decile source fixed, but changes one variable: admit only
signal-day cost/liquidity efficient candidates. The field is production-visible
and free-OHLCV derived:

- 20-day average dollar volume >= USD 200m
- signal-day range / close <= 10%

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_005_full_universe_alpha_score_top1_20d_candidate_pool as source


framework = source.framework

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260531-008"
STEM = "full_universe_alpha_score_cost_liquidity_candidate_pool"
TRIAL_FAMILY = "full_universe_alpha_score_candidate_pool_cost_liquidity"
CHANGED_VARIABLE = "full_universe_alpha_score_top1_20d_cost_liquidity_efficiency"
RULE_VERSION = "full_universe_alpha_score_top1_20d_cost_liquidity_efficiency_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_008_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_EFFICIENT_AVG_DOLLAR_VOLUME_20D = 200_000_000.0
MAX_SIGNAL_DAY_RANGE_CLOSE_PCT = 0.10


def _patch_framework() -> None:
    source._patch_framework()
    for module in (source, framework):
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


def _range_close_pct(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    date_value: str,
) -> float | None:
    rows = framework.ohlcv_helper._series(snapshot, ticker)
    idx = framework.ohlcv_helper._row_index(rows).get(date_value)
    if idx is None:
        return None
    high = framework.ohlcv_helper._value(rows[idx], "High")
    low = framework.ohlcv_helper._value(rows[idx], "Low")
    close = framework.ohlcv_helper._value(rows[idx], "Close")
    if high is None or low is None or close is None or close <= 0:
        return None
    return (float(high) - float(low)) / float(close)


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_candidates, source_audit = source._candidate_rows_for_window(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    filtered: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()

    for row in raw_candidates:
        avg_dollar_volume = float(row.get("avg_dollar_volume_20d") or 0.0)
        if avg_dollar_volume < MIN_EFFICIENT_AVG_DOLLAR_VOLUME_20D:
            audit["below_200m_avg_dollar_volume_20d"] += 1
            continue

        ticker = str(row.get("ticker") or "").upper()
        date_value = str(row.get("date") or "")
        range_close = _range_close_pct(snapshot, ticker, date_value)
        if range_close is None:
            audit["missing_signal_day_range_close_pct"] += 1
            continue
        if range_close > MAX_SIGNAL_DAY_RANGE_CLOSE_PCT:
            audit["range_close_above_10pct"] += 1
            continue

        filtered.append(
            {
                **row,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "signal_day_range_close_pct": framework.base._round(range_close, 6),
                "cost_liquidity_efficiency_bucket": "efficient",
                "cost_liquidity_efficiency_rule": {
                    "min_avg_dollar_volume_20d": MIN_EFFICIENT_AVG_DOLLAR_VOLUME_20D,
                    "max_signal_day_range_close_pct": MAX_SIGNAL_DAY_RANGE_CLOSE_PCT,
                },
            }
        )

    return filtered, {
        "dates_checked": source_audit.get("dates_checked"),
        "raw_top_decile_candidate_count_before_cost_liquidity": len(raw_candidates),
        "candidate_count": len(filtered),
        "candidate_days": len({row["date"] for row in filtered}),
        "unique_candidate_tickers": len({row["ticker"] for row in filtered}),
        "source_audit": source_audit,
        "cost_liquidity_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
    }


def _load_prior_result(experiment_id: str, filename: str) -> dict[str, Any] | None:
    path = REPO_ROOT / "data" / "experiments" / experiment_id / filename
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _prior_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    current = payload["delta_metrics"]["aggregate"]
    current_target = payload.get("target_trade_summary") or {}
    out: dict[str, Any] = {}
    for experiment_id, filename, label in [
        (
            "exp-20260531-005",
            "exp_20260531_005_full_universe_alpha_score_top1_20d_candidate_pool.json",
            "raw_top1",
        ),
        (
            "exp-20260531-007",
            "exp_20260531_007_full_universe_alpha_score_cooldown_candidate_pool.json",
            "cooldown",
        ),
    ]:
        prior = _load_prior_result(experiment_id, filename)
        if not prior:
            continue
        agg = (prior.get("delta_metrics") or {}).get("aggregate") or {}
        target = prior.get("target_trade_summary") or {}
        out[label] = {
            "experiment_id": experiment_id,
            "decision": prior.get("decision"),
            "ev_delta_sum": agg.get("expected_value_score_delta_sum"),
            "pnl_delta_sum": agg.get("total_pnl_delta_sum"),
            "max_drawdown_delta_max": agg.get("max_drawdown_delta_max"),
            "target_trades": target.get("total_trade_count"),
            "max_single_positive_share": target.get("max_single_positive_pnl_share"),
            "positive_hhi": target.get("positive_pnl_hhi"),
        }
    out["current_cost_liquidity"] = {
        "ev_delta_sum": current.get("expected_value_score_delta_sum"),
        "pnl_delta_sum": current.get("total_pnl_delta_sum"),
        "max_drawdown_delta_max": current.get("max_drawdown_delta_max"),
        "target_trades": current_target.get("total_trade_count"),
        "max_single_positive_share": current_target.get("max_single_positive_pnl_share"),
        "positive_hhi": current_target.get("positive_pnl_hhi"),
    }
    return out


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if gate4["passed"]
        else "rejected_full_universe_alpha_score_cost_liquidity_candidate_pool"
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
                "Full-universe PIT alpha_score top-decile candidates may keep "
                "the broad ranking edge with lower drawdown when admitted only "
                "in cost/liquidity efficient signal-day states."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260531-005",
                "exp-20260531-006",
                "exp-20260531-007",
                "exp-20260529-004",
            ],
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": "new_production_visible_cost_liquidity_field",
            "prediction": {
                "success_probability": 0.30,
                "expected_ev_delta": 0.50,
                "expected_pnl_delta": 10000.0,
                "main_failure_modes": [
                    "drawdown_still_failed",
                    "edge_eroded_by_liquidity_filter",
                    "window_regression",
                    "thin_sample",
                ],
                "confidence_reason": (
                    "Raw alpha_score top-1 had large aggregate EV but failed "
                    "drawdown/concentration; VBB accepted the same free-OHLCV "
                    "cost/liquidity field, so this tests an orthogonal "
                    "production-visible quality field rather than retuning "
                    "score thresholds."
                ),
                "recorded_at": "2026-05-31T08:06:03+00:00",
                "brier_score": round((0.30 - actual_success) ** 2, 6),
            },
            "parameters": {
                **payload["parameters"],
                "source_definition_fixed_from": "exp-20260531-005",
                "min_efficient_avg_dollar_volume_20d": MIN_EFFICIENT_AVG_DOLLAR_VOLUME_20D,
                "max_signal_day_range_close_pct": MAX_SIGNAL_DAY_RANGE_CLOSE_PCT,
                "changed_only": [
                    "after the exp-20260531-005 top-decile alpha_score candidate source is formed",
                    "keep candidates only when avg_dollar_volume_20d >= 200m and signal_day_range_close_pct <= 0.10",
                    "candidate score, top-1/day routing, 20-trading-day hold, notional, core logic, LLM/news, and live orders remain locked",
                ],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / ranking: alpha_score has a real top-quantile "
                    "edge, but it needs a production-visible friction/risk state "
                    "before it can become a robust default-off paper source."
                ),
                "2_history_check": {
                    "exp-20260531-005": (
                        "Raw top-1 alpha_score improved aggregate EV/PnL but "
                        "failed Gate 4 on +13.32pp drawdown drift and target "
                        "concentration."
                    ),
                    "exp-20260531-007": (
                        "A 20-trading-day same-ticker cooldown reduced "
                        "concentration but regressed late_strong and still "
                        "failed drawdown."
                    ),
                    "exp-20260531-006": (
                        "Full-universe quantile attribution found top-quantile "
                        "edge but no clean monotonic ladder."
                    ),
                    "exp-20260529-004": (
                        "Accepted VBB cost/liquidity support used the same "
                        "free-OHLCV thresholds on a different sleeve."
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
                    "exp_20260531_008_full_universe_alpha_score_cost_liquidity_candidate_pool.py"
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
                    "must not be promoted until a shared default-off adapter "
                    "computes the same PIT alpha_score surface and cost/liquidity "
                    "field in both production and replay."
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
                    "A positive replay lead requires a shared default-off paper "
                    "adapter, production report wiring, cost/liquidity field "
                    "parity, and focused tests before any activation review."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe attribution remains "
                "sparse. Skipped FINRA/VBB/VCP/Companyfacts/Form4/earnings-imminent "
                "nearby retunes because the playbook requires forward rows or "
                "materially new fields. This run keeps the alpha_score source, "
                "score weights, top-N, hold, notional, core logic, LLM/news, and "
                "live orders fixed while changing only cost/liquidity efficiency."
            ),
            "prior_candidate_pool_comparison": _prior_comparison(payload),
            "interpretation": (
                "The cost/liquidity efficient alpha_score paper source cleared "
                "Gate 4 as a replay-only lead, but no production/shared policy "
                "was promoted."
                if gate4["passed"]
                else (
                    "The cost/liquidity efficient alpha_score paper source did "
                    "not clear Gate 4. Do not promote it or continue nearby "
                    "alpha_score friction filters on frozen windows without "
                    "forward replacement-value rows or a richer score component."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows, a shared production/replay "
                "alpha_score adapter, or a materially richer component-level "
                "ranking field. Do not just mine alpha_score cost/liquidity "
                "thresholds on the same frozen replay."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "The alpha_score surface is rebuilt point-in-time using signal-date "
        "OHLCV/context. The only changed variable versus exp-20260531-005 is "
        "the signal-day cost/liquidity efficiency field. Paper entry is the "
        "next available open with production entry slippage; exit is 20 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
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
            "known_at",
            "alpha_score",
            "alpha_score_bucket",
            "alpha_score_rank_pct",
            "avg_dollar_volume_20d",
            "signal_day_range_close_pct",
            "cost_liquidity_efficiency_bucket",
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
            "# exp-20260531-008 Full-Universe Alpha-Score Cost/Liquidity Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: keep the exp-20260531-005 full-universe alpha_score top-decile source fixed, but admit only candidates with 20-day average dollar volume >= $200m and signal-day range/close <= 10%.",
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
            "## Prior Comparison",
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
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result is not promoted without a shared default-off adapter and parity tests.",
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
        "title": "Full-universe alpha-score cost/liquidity candidate pool",
        "status": payload["status"],
        "decision": payload["decision"],
        "json": framework.base._repo_rel(OUT_JSON),
        "card": framework.base._repo_rel(CARD_MD),
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
        "completed_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "failed_reasons": payload["gate4"]["failed_reasons"],
            "result_file": framework.base._repo_rel(OUT_JSON),
            "card_file": framework.base._repo_rel(CARD_MD),
            "artifact": framework.base._repo_rel(ARTIFACT_MD),
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
                    "prior_candidate_pool_comparison": payload[
                        "prior_candidate_pool_comparison"
                    ],
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
