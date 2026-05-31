"""exp-20260531-016: alpha-score market-regime candidate pool.

This alpha search keeps the rejected exp-20260531-005 full-universe
``alpha_score`` top-decile source fixed, but changes one variable: admit paper
candidates only when broad risk appetite confirms that the rank surface is
allowed to matter.

The deterministic, production-visible regime gate is:

- SPY signal-date close is above its 50-day moving average; and
- IWM 20-day return is at least SPY 20-day return.

Core signal generation, score weights, top-1/day routing, sizing, exits,
LLM/news replay, watchlists, and live/default orders are unchanged. No
JavaScript is used.
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

EXPERIMENT_ID = "exp-20260531-016"
STEM = "full_universe_alpha_score_market_regime_candidate_pool"
TRIAL_FAMILY = "full_universe_alpha_score_candidate_pool_regime_gate"
CHANGED_VARIABLE = "full_universe_alpha_score_market_risk_appetite_regime_gate_v1"
RULE_VERSION = "full_universe_alpha_score_top1_20d_market_risk_appetite_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_016_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MARKET_RET_DAYS = 20
SPY_MA_DAYS = 50


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


def _trailing_average(
    rows: list[dict[str, Any]],
    idx: int,
    days: int,
    field: str,
) -> float | None:
    if idx + 1 < days:
        return None
    values = [
        framework.ohlcv_helper._value(row, field)
        for row in rows[idx + 1 - days : idx + 1]
    ]
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return sum(clean) / len(clean)


def _close_return(
    rows: list[dict[str, Any]],
    idx: int,
    days: int,
) -> float | None:
    if idx < days:
        return None
    start = framework.ohlcv_helper._value(rows[idx - days], "Close")
    end = framework.ohlcv_helper._value(rows[idx], "Close")
    if not start or end is None:
        return None
    return (float(end) / float(start)) - 1.0


def _market_regime_context(
    snapshot: dict[str, list[dict[str, Any]]],
    date_value: str,
) -> dict[str, Any]:
    spy_rows = framework.ohlcv_helper._series(snapshot, "SPY")
    iwm_rows = framework.ohlcv_helper._series(snapshot, "IWM")
    spy_idx = framework.ohlcv_helper._row_index(spy_rows).get(date_value)
    iwm_idx = framework.ohlcv_helper._row_index(iwm_rows).get(date_value)
    if spy_idx is None or iwm_idx is None:
        return {
            "available": False,
            "market_regime_bucket": "missing_market_rows",
            "risk_appetite_regime_pass": False,
        }

    spy_close = framework.ohlcv_helper._value(spy_rows[spy_idx], "Close")
    spy_ma50 = _trailing_average(spy_rows, spy_idx, SPY_MA_DAYS, "Close")
    spy_ret20 = _close_return(spy_rows, spy_idx, MARKET_RET_DAYS)
    iwm_ret20 = _close_return(iwm_rows, iwm_idx, MARKET_RET_DAYS)
    if (
        spy_close is None
        or spy_ma50 is None
        or spy_ret20 is None
        or iwm_ret20 is None
    ):
        return {
            "available": False,
            "market_regime_bucket": "insufficient_market_history",
            "risk_appetite_regime_pass": False,
        }

    spy_above_ma50 = float(spy_close) >= float(spy_ma50)
    iwm_minus_spy_ret20 = float(iwm_ret20) - float(spy_ret20)
    iwm_confirms = iwm_minus_spy_ret20 >= 0.0
    passed = spy_above_ma50 and iwm_confirms
    if passed:
        bucket = "risk_appetite_confirmed"
    elif not spy_above_ma50:
        bucket = "spy_below_50d"
    else:
        bucket = "iwm_lagging_spy_20d"

    return {
        "available": True,
        "market_regime_bucket": bucket,
        "risk_appetite_regime_pass": passed,
        "spy_close": framework.base._round(spy_close, 4),
        "spy_ma50": framework.base._round(spy_ma50, 4),
        "spy_above_50d_ma": spy_above_ma50,
        "spy_ret20": framework.base._round(spy_ret20, 6),
        "iwm_ret20": framework.base._round(iwm_ret20, 6),
        "iwm_minus_spy_ret20": framework.base._round(iwm_minus_spy_ret20, 6),
    }


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
    regime_by_date: dict[str, dict[str, Any]] = {}

    for row in raw_candidates:
        date_value = str(row.get("date") or "")
        context = regime_by_date.get(date_value)
        if context is None:
            context = _market_regime_context(snapshot, date_value)
            regime_by_date[date_value] = context
        bucket = str(context.get("market_regime_bucket") or "unknown")
        audit[bucket] += 1
        if not context.get("risk_appetite_regime_pass"):
            continue

        filtered.append(
            {
                **row,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "market_regime_rule_version": RULE_VERSION,
                "rank_score_validity_regime_bucket": bucket,
                "market_regime_known_at": (
                    "after_signal_date_close_before_next_open_paper_entry"
                ),
                "market_regime_rule": {
                    "spy_close_must_be_above_50d_ma": True,
                    "iwm_20d_return_minus_spy_20d_return_min": 0.0,
                    "uses_only_signal_date_or_prior_ohlcv": True,
                },
                **{
                    key: value
                    for key, value in context.items()
                    if key
                    in {
                        "spy_close",
                        "spy_ma50",
                        "spy_above_50d_ma",
                        "spy_ret20",
                        "iwm_ret20",
                        "iwm_minus_spy_ret20",
                    }
                },
            }
        )

    return filtered, {
        "dates_checked": source_audit.get("dates_checked"),
        "raw_top_decile_candidate_count_before_market_regime": len(raw_candidates),
        "candidate_count": len(filtered),
        "candidate_days": len({row["date"] for row in filtered}),
        "unique_candidate_tickers": len({row["ticker"] for row in filtered}),
        "source_audit": source_audit,
        "market_regime_bucket_counts": dict(sorted(audit.items())),
        "regime_days_by_bucket": dict(
            sorted(
                Counter(
                    str(context.get("market_regime_bucket") or "unknown")
                    for context in regime_by_date.values()
                ).items()
            )
        ),
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
        (
            "exp-20260531-008",
            "exp_20260531_008_full_universe_alpha_score_cost_liquidity_candidate_pool.json",
            "cost_liquidity",
        ),
        (
            "exp-20260531-009",
            "exp_20260531_009_full_universe_alpha_score_resilient_rank_candidate_pool.json",
            "resilient_rank",
        ),
        (
            "exp-20260531-011",
            "exp_20260531_011_full_universe_alpha_score_breadth_aligned_candidate_pool.json",
            "breadth_aligned",
        ),
        (
            "exp-20260531-014",
            "exp_20260531_014_full_universe_alpha_score_low_volume_candidate_pool.json",
            "low_volume_bucket",
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
    out["current_market_regime"] = {
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
        else "rejected_full_universe_alpha_score_market_regime_candidate_pool"
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
                "Full-universe alpha_score should only route default-off paper "
                "candidates when broad risk appetite confirms the rank surface; "
                "requiring SPY above its 50-day average and IWM 20-day return "
                "at least SPY 20-day return may preserve the ranking edge while "
                "reducing old-window drawdown."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 6,
            "nearby_prior_experiments": [
                "exp-20260531-005",
                "exp-20260531-006",
                "exp-20260531-007",
                "exp-20260531-008",
                "exp-20260531-009",
                "exp-20260531-011",
                "exp-20260531-014",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "production_visible_market_regime_score_validity_bucket",
            "prediction": {
                "success_probability": 0.30,
                "expected_ev_delta": 0.75,
                "expected_pnl_delta": 15000.0,
                "main_failure_modes": [
                    "drawdown_drift_too_high",
                    "target_concentration_failed",
                    "late_strong_regression",
                    "sample_too_small",
                ],
                "confidence_reason": (
                    "Prior alpha_score paper variants had large aggregate EV "
                    "but failed drawdown/concentration. The playbook asks for "
                    "regime buckets before any adapter promotion."
                ),
                "recorded_at": "2026-05-31T16:08:17+00:00",
                "brier_score": round((0.30 - actual_success) ** 2, 6),
            },
            "parameters": {
                **payload["parameters"],
                "source_definition_fixed_from": "exp-20260531-005",
                "market_ret_days": MARKET_RET_DAYS,
                "spy_ma_days": SPY_MA_DAYS,
                "changed_only": [
                    "after the exp-20260531-005 top-decile alpha_score candidate source is formed",
                    "keep candidates only when SPY is above its 50-day moving average",
                    "keep candidates only when IWM 20-day return is at least SPY 20-day return",
                    "candidate score weights, top-1/day routing, 20-trading-day hold, notional, core logic, LLM/news, and live orders remain locked",
                ],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / ranking: alpha_score has a real "
                    "top-quantile edge, but the rank surface may only be valid "
                    "in broad risk-appetite regimes."
                ),
                "2_history_check": {
                    "exp-20260531-005": (
                        "Raw top-1 alpha_score improved aggregate EV/PnL but "
                        "failed Gate 4 on +13.32pp drawdown drift and target "
                        "concentration."
                    ),
                    "exp-20260531-006": (
                        "Full-universe quantile attribution found a top-vs-bottom "
                        "edge but no clean monotonic ladder."
                    ),
                    "exp-20260531-007": (
                        "Same-ticker cooldown reduced concentration but regressed "
                        "late_strong and still failed drawdown."
                    ),
                    "exp-20260531-008": (
                        "Cost/liquidity filtering preserved EV/PnL but still "
                        "failed drawdown and concentration."
                    ),
                    "exp-20260531-009": (
                        "Drawdown/volatility resilient ranking regressed windows "
                        "and worsened concentration."
                    ),
                    "exp-20260531-011": (
                        "Breadth-aligned component gate still failed drawdown and "
                        "concentration."
                    ),
                    "exp-20260531-014": (
                        "Low-volume predictability bucket still failed windows, "
                        "drawdown, and concentration."
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
                    "exp_20260531_016_full_universe_alpha_score_market_regime_candidate_pool.py"
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
                    "computes the same PIT alpha_score surface and market regime "
                    "gate in both production and replay."
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
                    "adapter, production report wiring, market-regime parity, "
                    "and focused tests before any activation review."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe attribution remains "
                "sparse. SEC Item 8.01 filing-body subtype was data-blocked: "
                "the canonical pure-8.01 rows did not have usable text coverage. "
                "Skipped FINRA/VBB/VCP/Companyfacts/Form4/earnings-imminent "
                "nearby retunes because the playbook requires forward rows or "
                "materially new fields. This run keeps the alpha_score source, "
                "score weights, top-N, hold, notional, core logic, LLM/news, "
                "and live orders fixed while changing only the market regime "
                "admission gate."
            ),
            "prior_candidate_pool_comparison": _prior_comparison(payload),
            "interpretation": (
                "The market-regime alpha_score paper source cleared Gate 4 as "
                "a replay-only lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The market-regime alpha_score paper source did not clear "
                    "Gate 4. Do not promote it or continue nearby alpha_score "
                    "state-gate mining on frozen windows without forward "
                    "replacement-value rows or a materially richer validity field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows, a shared production/replay "
                "alpha_score adapter, or a materially richer rank-validity "
                "field. Do not just mine alpha_score state gates on the same "
                "frozen replay."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "The alpha_score surface is rebuilt point-in-time using signal-date "
        "OHLCV/context. The only changed variable versus exp-20260531-005 is "
        "the market risk-appetite regime admission gate. Paper entry is the "
        "next available open with production entry slippage; exit is 20 trading "
        "days after the signal with target-side sell slippage and "
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
            "alpha_score_components",
            "rank_score_validity_regime_bucket",
            "spy_above_50d_ma",
            "iwm_minus_spy_ret20",
            "avg_dollar_volume_20d",
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
            "# exp-20260531-016 Full-Universe Alpha-Score Market-Regime Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: keep the exp-20260531-005 full-universe alpha_score top-decile source fixed, but admit candidates only when SPY is above its 50-day moving average and IWM 20-day return is at least SPY 20-day return.",
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
        "title": "Full-universe alpha-score market-regime candidate pool",
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
