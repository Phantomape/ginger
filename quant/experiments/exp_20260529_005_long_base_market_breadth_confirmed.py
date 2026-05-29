"""exp-20260529-005: long-base breakout with market-breadth confirmation.

This alpha search tests one stock-only, free-OHLCV candidate-pool source:
the previously rejected 63-day long-base breakout candidate source, but only
on signal dates where the existing volume-breadth participation context passes.

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

import exp_20260526_005_long_base_breakout_paper_sleeve as long_base
import exp_20260526_013_volume_breadth_breakout_sleeve as vbb_source
import exp_20260528_037_ticker_accumulation_quality_breakout as framework


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260529-005"
STEM = "long_base_market_breadth_confirmed"
TRIAL_FAMILY = "long_base_market_breadth_confirmed_candidate_pool"
CHANGED_VARIABLE = "long_base_market_breadth_confirmed_candidate_source_v1"
RULE_VERSION = "long_base_63d_market_breadth_confirmed_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    framework.AFTER_AGG_JSON = AFTER_AGG_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.DOC_TICKET_JSON = DOC_TICKET_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.MAX_PAPER_TRADES_PER_DAY = 1
    framework.MIN_TARGET_TRADES = 20
    framework.MIN_TARGET_WINDOWS = 3
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    del universe
    dates = [
        date
        for date in framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    source_universe = sorted(set(snapshot).difference(long_base.EXCLUDED_TICKERS))
    breadth_by_date = vbb_source._breadth_context_by_date(
        snapshot,
        dates,
        source_universe,
    )
    long_base_candidates = long_base._candidate_rows_for_window(
        snapshot,
        cfg,
        source_universe,
        before_result,
    )
    filtered: list[dict[str, Any]] = []
    reject_counts: Counter[str] = Counter()
    for row in long_base_candidates:
        context = breadth_by_date.get(str(row.get("date") or "")) or {}
        if not context.get("volume_breadth_thrust_passed"):
            reject_counts["market_breadth_context_not_passed"] += 1
            continue
        filtered.append(
            {
                **row,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "long_base_rule_version": row.get("long_base_breakout_rule_version"),
                "market_breadth_confirmation_rule_version": vbb_source.RULE_VERSION,
                "market_breadth_passed": True,
                "market_breadth_context": context,
                "volume_breadth_fraction": context.get("volume_breadth_fraction"),
                "market_up_fraction": context.get("market_up_fraction"),
                "above_50d_fraction": context.get("above_50d_fraction"),
                "known_at": "after_signal_date_close_before_next_open_paper_entry",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    label = next(
        (
            window_label
            for window_label, window_cfg in framework.base.WINDOWS.items()
            if window_cfg is cfg
        ),
        str(cfg.get("start")),
    )
    long_base_audit = dict(long_base.LONG_BASE_AUDIT.get(label) or {})
    breadth_pass_dates = [
        date
        for date, context in breadth_by_date.items()
        if context.get("volume_breadth_thrust_passed")
    ]
    filtered.sort(
        key=lambda row: (
            row["date"],
            -float(row["long_base_breakout_score"]),
            -float(row["rs20_vs_spy"]),
            -float(row["volume_ratio20"]),
            -float(row["volume_breadth_fraction"] or 0.0),
            row["ticker"],
        )
    )
    return filtered, {
        "dates_checked": len(dates),
        "long_base_raw_candidate_count": len(long_base_candidates),
        "candidate_count": len(filtered),
        "candidate_days": len({row["date"] for row in filtered}),
        "unique_candidate_tickers": len({row["ticker"] for row in filtered}),
        "breadth_pass_days": len(breadth_pass_dates),
        "breadth_pass_day_fraction": framework.base._round(
            len(breadth_pass_dates) / len(dates) if dates else None,
            6,
        ),
        "reject_counts": dict(sorted(reject_counts.items())),
        "long_base_source_audit": long_base_audit,
        "sample_breadth_context": {
            date: breadth_by_date[date] for date in breadth_pass_dates[:10]
        },
        "rule_version": RULE_VERSION,
        "breadth_rule_version": vbb_source.RULE_VERSION,
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "promising_replay_only_long_base_market_breadth_confirmed"
        if gate4["passed"]
        else "rejected_long_base_market_breadth_confirmed"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.32,
        "expected_ev_delta": 0.12,
        "expected_pnl_delta": 2500.0,
        "main_failure_modes": [
            "late_strong_regression",
            "sample_too_small",
            "breadth_condition_not_discriminating",
        ],
        "confidence_reason": (
            "Long-base breakout failed only because late_strong regressed while "
            "VBB market participation is a validated free-OHLCV context; sample "
            "and old-window stability remain risks."
        ),
        "recorded_at": "2026-05-29T04:07:03+00:00",
        "brier_score": round((0.32 - actual_success) ** 2, 6),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Long-base 63-day breakout candidates may have cleaner replacement "
                "value when the signal date also passes the existing market "
                "volume-breadth participation context."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": "long_base_market_breadth_confirmed_v1",
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260526-005",
                "exp-20260526-013",
                "exp-20260526-014",
                "exp-20260528-036",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "orthogonal_free_ohlcv_market_breadth_confirmation"
            ),
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(long_base.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": framework.MAX_PAPER_TRADES_PER_DAY,
                "source_definition": [
                    "long-base 63-day breakout from exp-20260526-005",
                    "same signal date must pass exp-20260526-013 market volume-breadth context",
                    "stock/ETF exclusions inherited from long-base source",
                    "top-1 selected paper entry per signal date",
                ],
                "long_base_filters_locked_from_exp_20260526_005": {
                    "high_lookback_days": long_base.HIGH_LOOKBACK_DAYS,
                    "min_base_days_without_fresh_high": long_base.MIN_BASE_DAYS_WITHOUT_FRESH_HIGH,
                    "max_ret20_before_breakout": long_base.MAX_RET20_BEFORE_BREAKOUT,
                    "min_volume_ratio_20": long_base.MIN_VOLUME_RATIO_20,
                    "min_close_location": long_base.MIN_CLOSE_LOCATION,
                    "min_close": long_base.MIN_CLOSE,
                    "min_avg_dollar_volume_20": long_base.MIN_AVG_DOLLAR_VOLUME_20,
                    "min_rs20_vs_spy": long_base.MIN_RS20_VS_SPY,
                },
                "market_breadth_context_locked_from_exp_20260526_013": {
                    "min_volume_breadth_fraction": vbb_source.MIN_VOLUME_BREADTH_FRACTION,
                    "min_market_up_fraction": vbb_source.MIN_MARKET_UP_FRACTION,
                    "min_above_50d_fraction": vbb_source.MIN_ABOVE_50D_FRACTION,
                    "min_breadth_eligible_tickers": vbb_source.MIN_BREADTH_ELIGIBLE_TICKERS,
                    "volume_lookback_days": vbb_source.VOLUME_LOOKBACK_DAYS,
                },
                "selection_rank": [
                    "signal_date",
                    "long_base_breakout_score desc",
                    "rs20_vs_spy desc",
                    "volume_ratio20 desc",
                    "volume_breadth_fraction desc",
                    "ticker asc",
                ],
                "locked_variables": [
                    "core universe membership",
                    "core signal generation",
                    "core ranking",
                    "core position sizing",
                    "core exits",
                    "portfolio heat",
                    "slot rules",
                    "LLM/news replay",
                    "watchlists",
                    "live/default orders",
                    "long-base source thresholds",
                    "market breadth thresholds",
                ],
                "acceptance": payload["parameters"]["acceptance"],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: 63-day long-base breakouts may "
                    "work only when market-wide up-volume participation confirms "
                    "the signal date. This follows the playbook's free-data "
                    "candidate-pool direction and avoids LLM/state-surface retunes."
                ),
                "2_history_check": {
                    "exp-20260526-005": (
                        "Long-base breakout failed Gate 4: aggregate EV -0.0823, "
                        "PnL +$4,715.76, 2/3 windows improved, late_strong "
                        "regressed. Retry requires orthogonal source confirmation."
                    ),
                    "exp-20260526-013_and_014": (
                        "Volume-breadth breakout established and shared a "
                        "production-visible market participation context. This run "
                        "uses its context as confirmation; it does not retune VBB."
                    ),
                    "exp-20260528-036": (
                        "Sector-breadth plus market-breadth agreement failed due a "
                        "late_strong regression. This run tests a different base "
                        "breakout source, not sector breadth."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate "
                    "EV/PnL; 3/3 EV-improved windows; no PnL-regressed window; "
                    ">=20 paper trades across all 3 windows; drawdown drift <=0.5pp; "
                    "survival >=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260529_005_long_base_market_breadth_confirmed.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe attribution remains "
                "sparse; skipped Companyfacts/VBB/VCP scalar retunes because the "
                "playbook asks for forward rows; skipped pure long-base threshold "
                "retunes because exp-20260526-005 explicitly requires an orthogonal "
                "confirmation field."
            ),
            "interpretation": (
                "The long-base market-breadth confirmed sleeve cleared Gate 4 as "
                "a replay-only lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The long-base market-breadth confirmed sleeve did not clear "
                    "Gate 4. Do not promote it or retry nearby long-base + breadth "
                    "thresholds on the same frozen windows without forward paper "
                    "rows or a materially different source-quality field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If revisited, require forward paper outcomes or a materially "
                "different production-visible event/source confirmation field. Do "
                "not just retune the long-base or market-breadth thresholds."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signals use only close-of-day OHLCV and same-day breadth context known "
        "after the signal-date close; paper entry is the next available open "
        "with production entry slippage; exit is ten trading days after the "
        "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
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
            "long_base_breakout_score",
            "volume_breadth_fraction",
            "market_up_fraction",
            "above_50d_fraction",
        ],
    )
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for 20-day and 63-day relative strength",
        "derived prior 63-day high known at signal-date close",
        "derived prior fresh-high spacing known at signal-date close",
        "derived same-date volume-breadth participation context",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate3"]["candidate_pool_changed"] = True
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "default_off_paper_only": True,
        "production_watchlist_changed": False,
        "production_orders_changed": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "promotion_requirement": (
            "A retained result would still require a shared default-off paper "
            "adapter, daily report exposure, forward replacement-value ledger, "
            "and parity tests before any production/report behavior changes."
        ),
    }
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
        framework.base._repo_rel(OUT_JSON),
        framework.base._repo_rel(BEFORE_AGG_JSON),
        framework.base._repo_rel(AFTER_AGG_JSON),
        framework.base._repo_rel(LOG_JSON),
        framework.base._repo_rel(TICKET_JSON),
        framework.base._repo_rel(DOC_TICKET_JSON),
        framework.base._repo_rel(ARTIFACT_MD),
        framework.base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw long-base | Confirmed candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["candidate_audits"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} | {confirmed} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=audit["long_base_raw_candidate_count"],
                confirmed=audit["candidate_count"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Long-Base Market-Breadth Confirmed",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper source admits the existing long-base 63-day breakout candidates only when same-date market volume-breadth participation passes.",
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
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Candidate Audit",
            "",
            "```json",
            json.dumps(payload["candidate_audits"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
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
        "title": "Long-base market-breadth confirmed paper sleeve",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "json": framework.base._repo_rel(OUT_JSON),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    framework.base._write_json(DOC_TICKET_JSON, ticket_payload)
    framework.base._write_text(ARTIFACT_MD, _build_report(payload))
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
                    "artifact": framework.base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
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
