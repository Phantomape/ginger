"""exp-20260531-007: deconcentrated full-universe alpha-score paper pool.

This alpha search keeps the rejected exp-20260531-005 candidate definition
fixed and changes one variable only: admitted paper candidates use a
20-trading-day same-ticker cooldown. The goal is to keep the broad alpha_score
replacement-value lead while reducing APP-like concentration and old-window
drawdown.

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

EXPERIMENT_ID = "exp-20260531-007"
STEM = "full_universe_alpha_score_cooldown_candidate_pool"
TRIAL_FAMILY = "full_universe_alpha_score_candidate_pool_deconcentration"
CHANGED_VARIABLE = "full_universe_alpha_score_top1_20d_same_ticker_20td_cooldown"
RULE_VERSION = "full_universe_alpha_score_top1_20d_same_ticker_20td_cooldown_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_007_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

COOLDOWN_TRADING_DAYS = 20
RAW_TOP1_RESULT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260531-005"
    / "exp_20260531_005_full_universe_alpha_score_top1_20d_candidate_pool.json"
)


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

    framework._candidate_rows_for_window = source._candidate_rows_for_window
    framework._select_paper_trades = _select_paper_trades_with_cooldown
    framework._build_report = _build_report


def _trading_day_index(snapshot: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {
        str(date): idx
        for idx, date in enumerate(framework.ohlcv_helper._trading_dates(snapshot))
    }


def _select_paper_trades_with_cooldown(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    last_selected_idx_by_ticker: dict[str, int] = {}
    date_idx = _trading_day_index(snapshot)

    for row in candidates:
        date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        current_idx = date_idx.get(date)

        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[date] >= framework.MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue

        last_idx = last_selected_idx_by_ticker.get(ticker)
        if (
            current_idx is not None
            and last_idx is not None
            and current_idx - last_idx <= COOLDOWN_TRADING_DAYS
        ):
            filtered.append(
                {
                    **row,
                    "filter_reason": "same_ticker_cooldown_active",
                    "same_ticker_cooldown_trading_days": COOLDOWN_TRADING_DAYS,
                    "cooldown_trade_days_since_last_admission": current_idx - last_idx,
                }
            )
            continue

        trade = framework.base._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue

        selected.append(
            {
                **trade,
                "same_ticker_cooldown_trading_days": COOLDOWN_TRADING_DAYS,
                "cooldown_trade_days_since_last_admission": (
                    None if last_idx is None or current_idx is None else current_idx - last_idx
                ),
            }
        )
        if current_idx is not None:
            last_selected_idx_by_ticker[ticker] = current_idx
        used_date_counts[date] += 1

    return selected, filtered


def _load_raw_top1_comparison(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not RAW_TOP1_RESULT.exists():
        return None
    with RAW_TOP1_RESULT.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    current = payload["delta_metrics"]["aggregate"]
    raw_agg = (raw.get("delta_metrics") or {}).get("aggregate") or {}
    raw_target = raw.get("target_trade_summary") or {}
    current_target = payload.get("target_trade_summary") or {}
    return {
        "raw_top1_experiment_id": raw.get("experiment_id"),
        "raw_top1_decision": raw.get("decision"),
        "raw_ev_delta_sum": raw_agg.get("expected_value_score_delta_sum"),
        "cooldown_ev_delta_sum": current.get("expected_value_score_delta_sum"),
        "raw_pnl_delta_sum": raw_agg.get("total_pnl_delta_sum"),
        "cooldown_pnl_delta_sum": current.get("total_pnl_delta_sum"),
        "raw_max_drawdown_delta_max": raw_agg.get("max_drawdown_delta_max"),
        "cooldown_max_drawdown_delta_max": current.get("max_drawdown_delta_max"),
        "raw_target_trades": raw_target.get("total_trade_count"),
        "cooldown_target_trades": current_target.get("total_trade_count"),
        "raw_max_single_positive_share": raw_target.get("max_single_positive_pnl_share"),
        "cooldown_max_single_positive_share": current_target.get(
            "max_single_positive_pnl_share"
        ),
        "raw_positive_hhi": raw_target.get("positive_pnl_hhi"),
        "cooldown_positive_hhi": current_target.get("positive_pnl_hhi"),
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if gate4["passed"]
        else "rejected_full_universe_alpha_score_cooldown_candidate_pool"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    raw_comparison = _load_raw_top1_comparison(payload)

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Full-universe PIT alpha_score top-1 candidates may keep most "
                "replacement-value edge while reducing APP-like concentration "
                "and old_thin drawdown when admitted candidates use a "
                "20-trading-day same-ticker cooldown."
            ),
            "change_type": "default_off_paper_candidate_pool_deconcentration",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260531-005",
                "exp-20260531-006",
                "exp-20260530-022",
            ],
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": "full_universe_pit_ranking_surface_deconcentrated_candidate_source",
            "prediction": {
                "success_probability": 0.32,
                "expected_ev_delta": 0.50,
                "expected_pnl_delta": 10000.0,
                "main_failure_modes": [
                    "drawdown_still_failed",
                    "edge_eroded_by_cooldown",
                    "mid_weak_regression",
                    "concentration_still_failed",
                ],
                "confidence_reason": (
                    "Raw alpha_score top-1 had large three-window EV/PnL but "
                    "failed drawdown and APP concentration; a hold-length "
                    "same-ticker cooldown is a distinct production-visible "
                    "deconcentration variable, not another score threshold."
                ),
                "recorded_at": "2026-05-31T07:13:29+00:00",
                "brier_score": round((0.32 - actual_success) ** 2, 6),
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / risk allocation: the full-universe PIT "
                    "alpha_score source has real edge, but needs deconcentration "
                    "before it can become a paper adapter candidate."
                ),
                "2_history_check": {
                    "exp-20260531-005": (
                        "Raw top-1 alpha_score candidate source improved all three "
                        "windows by +6.6893 EV and +$125,182.69 PnL but failed "
                        "Gate 4 on +13.32pp max-drawdown drift and APP/HHI "
                        "concentration."
                    ),
                    "exp-20260531-006": (
                        "Read-only full-universe quantile attribution found a "
                        "positive pooled top-minus-bottom 5d spread but no clean "
                        "monotonic ladder and a negative mid_weak spread."
                    ),
                    "exp-20260530-022": (
                        "Filled-trade alpha_score attribution was rank-degenerate, "
                        "so full-universe candidate-pool evidence is required."
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
                    "exp_20260531_007_full_universe_alpha_score_cooldown_candidate_pool.py"
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
                    "is not promoted until a shared default-off adapter computes "
                    "the same PIT alpha_score surface and same-ticker cooldown in "
                    "both production and replay."
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
                    "adapter, production report wiring, cooldown state parity, "
                    "and focused tests before any activation review."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe attribution remains "
                "sparse. Skipped FINRA/VBB/VCP/Companyfacts/Form4/earnings-imminent "
                "nearby retunes because the playbook requires forward rows or "
                "materially new fields. This run keeps the alpha_score source, "
                "hold, notional, rank surface, core logic, LLM/news, and live "
                "orders fixed while changing only same-ticker candidate cooldown."
            ),
            "raw_top1_comparison": raw_comparison,
            "interpretation": (
                "The deconcentrated alpha_score paper source cleared Gate 4 as "
                "a replay-only lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The deconcentrated alpha_score paper source did not clear "
                    "Gate 4. Do not promote it or continue cooldown/minor "
                    "deconcentration retunes on frozen windows without forward "
                    "replacement-value rows or a richer ranking component."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows, a shared production/replay "
                "alpha_score adapter, or a materially richer risk-aware ranking "
                "component. Do not just mine alpha_score thresholds or cooldown "
                "lengths on the same frozen replay."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"].update(
        {
            "source_definition_fixed_from": "exp-20260531-005",
            "same_ticker_cooldown_trading_days": COOLDOWN_TRADING_DAYS,
            "changed_only": [
                "after a ticker is admitted to the paper sleeve, skip the same ticker for the next 20 trading days",
                "same-day replacement remains rank-ordered by PIT alpha_score within the top-decile liquid stock candidates",
            ],
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "The alpha_score surface is rebuilt point-in-time using signal-date "
        "OHLCV/context. Paper entry is the next available open with production "
        "entry slippage; exit is 20 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT. The only changed "
        "variable versus exp-20260531-005 is same-ticker admission cooldown."
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
            "same_ticker_cooldown_trading_days",
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
    raw_cmp = payload.get("raw_top1_comparison") or {}
    raw_lines = [
        "## Versus Raw Top-1",
        "",
        f"- raw EV delta: `{raw_cmp.get('raw_ev_delta_sum')}`; cooldown EV delta: `{raw_cmp.get('cooldown_ev_delta_sum')}`",
        f"- raw PnL delta: `${raw_cmp.get('raw_pnl_delta_sum')}`; cooldown PnL delta: `${raw_cmp.get('cooldown_pnl_delta_sum')}`",
        f"- raw max DD drift: `{raw_cmp.get('raw_max_drawdown_delta_max')}`; cooldown max DD drift: `{raw_cmp.get('cooldown_max_drawdown_delta_max')}`",
        f"- raw max single positive share: `{raw_cmp.get('raw_max_single_positive_share')}`; cooldown: `{raw_cmp.get('cooldown_max_single_positive_share')}`",
        f"- raw positive HHI: `{raw_cmp.get('raw_positive_hhi')}`; cooldown: `{raw_cmp.get('cooldown_positive_hhi')}`",
        "",
    ]
    return "\n".join(
        [
            "# exp-20260531-007 Full-Universe Alpha-Score Cooldown Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: keep the exp-20260531-005 full-universe alpha_score top-decile candidate source fixed, but add a 20-trading-day same-ticker admission cooldown before the top-1 daily paper selection.",
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
            *raw_lines,
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
        "title": "Full-universe alpha-score cooldown candidate pool",
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
                    "raw_top1_comparison": payload["raw_top1_comparison"],
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
