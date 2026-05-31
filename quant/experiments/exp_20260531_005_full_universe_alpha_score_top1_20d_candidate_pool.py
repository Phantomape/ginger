"""exp-20260531-005: full-universe alpha-score top-1 paper candidate pool.

This alpha search tests one production-visible, free-data candidate-pool
source: each signal day, rebuild the point-in-time cross-sectional
``alpha_score`` surface, rank the full available stock universe, and admit the
best liquid top-decile candidate into a default-off paper sleeve.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260528_037_ticker_accumulation_quality_breakout as framework


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from entry_day_ranking_attribution import _context_for_asof, load_ohlcv_snapshot  # noqa: E402


EXPERIMENT_ID = "exp-20260531-005"
STEM = "full_universe_alpha_score_top1_20d_candidate_pool"
TRIAL_FAMILY = "full_universe_alpha_score_candidate_pool"
CHANGED_VARIABLE = "full_universe_alpha_score_top1_20d_candidate_source_v1"
RULE_VERSION = "full_universe_alpha_score_top1_20d_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_005_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

HOLD_DAYS = 20
AVG_DOLLAR_VOLUME_DAYS = 20
MIN_AVG_DOLLAR_VOLUME_20D = 40_000_000.0
ALLOWED_ALPHA_BUCKETS = {"top_decile"}
ADDITIONAL_NON_STOCK_EXCLUDED_TICKERS = {"SNXX"}
EXCLUDED_TICKERS = set(framework.EXCLUDED_TICKERS).union(
    ADDITIONAL_NON_STOCK_EXCLUDED_TICKERS
)


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
    framework.ARTIFACT_MD = CARD_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.MAX_PAPER_TRADES_PER_DAY = 1
    framework.MIN_TARGET_TRADES = 20
    framework.MIN_TARGET_WINDOWS = 3
    framework.base.HOLD_DAYS = HOLD_DAYS
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _avg_dollar_volume(
    rows: list[dict[str, Any]],
    idx: int,
    days: int,
) -> float | None:
    if idx + 1 < days:
        return None
    values: list[float] = []
    for row in rows[idx + 1 - days : idx + 1]:
        close = framework.ohlcv_helper._value(row, "Close")
        volume = framework.ohlcv_helper._value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(float(close) * float(volume))
    return sum(values) / len(values) if values else None


def _rank_context_for_window(cfg: dict[str, str]) -> dict[pd.Timestamp, dict[str, Any]]:
    snapshot_path = REPO_ROOT / str(cfg["snapshot"])
    ohlcv = load_ohlcv_snapshot(str(snapshot_path))
    all_dates: set[pd.Timestamp] = set()
    for frame in ohlcv.values():
        all_dates.update(frame.loc[str(cfg["start"]) : str(cfg["end"])].index)
    contexts: dict[pd.Timestamp, dict[str, Any]] = {}
    for asof_ts in sorted(all_dates):
        contexts[asof_ts] = _context_for_asof(ohlcv, asof_ts)
    return contexts


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.ohlcv_helper._baseline_entries(before_result)
    dates = [
        date_value
        for date_value in framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    contexts = _rank_context_for_window(cfg)
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    eligible_universe = set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)

    for date_value in dates:
        context = contexts.get(pd.Timestamp(date_value))
        if not context:
            audit["missing_rank_context"] += 1
            continue
        rank_map = context.get("rank_map") or {}
        ranked = sorted(
            rank_map.items(),
            key=lambda item: (
                -(float(item[1].get("alpha_score") or -math.inf)),
                str(item[0]),
            ),
        )
        for ticker, score_info in ranked:
            ticker = str(ticker).upper()
            if ticker not in eligible_universe:
                audit["excluded_or_not_in_universe"] += 1
                continue
            alpha_score = score_info.get("alpha_score")
            if alpha_score is None:
                audit["missing_alpha_score"] += 1
                continue
            alpha_bucket = str(score_info.get("alpha_score_bucket") or "")
            if alpha_bucket not in ALLOWED_ALPHA_BUCKETS:
                audit["not_top_decile"] += 1
                break

            rows = framework.ohlcv_helper._series(snapshot, ticker)
            idx = framework.ohlcv_helper._row_index(rows).get(date_value)
            if idx is None:
                audit["missing_signal_date_row"] += 1
                continue
            avg_dollar_volume = _avg_dollar_volume(rows, idx, AVG_DOLLAR_VOLUME_DAYS)
            if avg_dollar_volume is None:
                audit["missing_avg_dollar_volume"] += 1
                continue
            if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
                audit["low_avg_dollar_volume"] += 1
                continue

            close = framework.ohlcv_helper._value(rows[idx], "Close")
            volume = framework.ohlcv_helper._value(rows[idx], "Volume")
            if close is None or volume is None:
                audit["missing_close_or_volume"] += 1
                continue
            close_location = framework._close_location(rows[idx])
            ab_entries = entries_by_date.get(date_value, [])
            components = score_info.get("alpha_score_components") or {}
            candidates.append(
                {
                    "ticker": ticker,
                    "date": date_value,
                    "strategy": STEM,
                    "rule_version": RULE_VERSION,
                    "alpha_score": framework.base._round(alpha_score, 6),
                    "alpha_score_bucket": alpha_bucket,
                    "alpha_score_rank_pct": framework.base._round(
                        score_info.get("alpha_score_rank_pct"),
                        6,
                    ),
                    "alpha_score_components": {
                        key: framework.base._round(value, 6)
                        for key, value in sorted(components.items())
                    },
                    "close": framework.base._round(close, 4),
                    "volume": framework.base._round(volume, 2),
                    "avg_dollar_volume_20d": framework.base._round(
                        avg_dollar_volume,
                        2,
                    ),
                    "signal_close_location": framework.base._round(close_location, 6),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "known_at": "after_signal_date_close_before_next_open_paper_entry",
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["alpha_score"]),
            float(row["alpha_score_rank_pct"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "rank_context_days": len(contexts),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if gate4["passed"]
        else "rejected_full_universe_alpha_score_top1_20d_candidate_pool"
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
                "Full-universe PIT alpha_score top-ranked liquid stocks may form "
                "a cleaner default-off paper candidate pool than raw OHLCV pattern "
                "expansion."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260524-028",
                "exp-20260530-021",
                "exp-20260530-022",
            ],
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": "full_universe_pit_ranking_surface_candidate_source",
            "prediction": {
                "success_probability": 0.28,
                "expected_ev_delta": 0.25,
                "expected_pnl_delta": 5000.0,
                "main_failure_modes": [
                    "mid_weak_regression",
                    "non_monotonic_rank_surface",
                    "drawdown_drift",
                    "core_overlap",
                ],
                "confidence_reason": (
                    "Full-universe attribution had positive pooled top-bottom "
                    "10d/20d spreads, but 5d monotonicity failed and mid_weak "
                    "was weak."
                ),
                "recorded_at": "2026-05-31T04:08:21+00:00",
                "brier_score": round((0.28 - actual_success) ** 2, 6),
            },
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(EXCLUDED_TICKERS),
                "additional_non_stock_excluded_tickers": sorted(
                    ADDITIONAL_NON_STOCK_EXCLUDED_TICKERS
                ),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": HOLD_DAYS,
                "max_paper_trades_per_day": framework.MAX_PAPER_TRADES_PER_DAY,
                "allowed_alpha_score_buckets": sorted(ALLOWED_ALPHA_BUCKETS),
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "source_definition": [
                    "rebuild entry_day_ranking_attribution alpha_score surface at signal-date close",
                    "stock ticker only, excluding ETFs, commodity proxies, and known non-stock artifacts",
                    "candidate must be in the alpha_score top decile",
                    "20-day average dollar volume >= 40 million",
                    "top-1 admitted paper entry per signal date after same-ticker core-overlap skip",
                    "next-open paper entry and 20-trading-day paper exit",
                ],
                "selection_rank": [
                    "signal_date",
                    "alpha_score desc",
                    "alpha_score_rank_pct asc",
                    "avg_dollar_volume_20d desc",
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
                ],
                "acceptance": payload["parameters"]["acceptance"],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "ranking / candidate_pool: the full-universe PIT alpha_score "
                    "surface may identify better replacement candidates outside "
                    "the already-filled core trade set."
                ),
                "2_history_check": {
                    "exp-20260524-028": (
                        "Raw alpha_score monotonicity inside filled core trades "
                        "failed because nearly all filled trades were already top-ranked."
                    ),
                    "exp-20260530-022": (
                        "Entry-day filled-trade ranking was proposed because the "
                        "filled set was degenerate; it could not answer full-universe "
                        "replacement value."
                    ),
                    "exp-20260530-021": (
                        "Full-universe read-only attribution produced 3551 "
                        "observations with positive pooled 10d/20d top-bottom "
                        "spreads, but no tradeable paper candidate replay."
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
                    "exp_20260531_005_full_universe_alpha_score_top1_20d_candidate_pool.py"
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
                    "the same alpha_score surface in production and replay."
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
                    "A positive replay lead would require a shared default-off "
                    "paper adapter, production report wiring, and parity tests."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe attribution remains "
                "sparse. Skipped 13F because local rows are skipped-only and "
                "exp-20260527-906 already records the PIT coverage blocker. "
                "Skipped FINRA/VBB/VCP/Companyfacts/Form4/earnings-imminent "
                "nearby retunes because playbook requires forward rows or "
                "materially new fields."
            ),
            "interpretation": (
                "The full-universe alpha_score top-1 paper source cleared Gate 4 "
                "as a replay-only lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The full-universe alpha_score top-1 paper source did not "
                    "clear Gate 4. Do not promote it or convert alpha_score into "
                    "candidate-pool routing on the frozen windows without a "
                    "stronger replacement-value field or forward paper rows."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If revisited, use forward replacement-value rows, a full shared "
                "production/replay alpha_score adapter, or a materially richer "
                "ranking component; do not just mine alpha_score thresholds."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "The alpha_score surface is rebuilt point-in-time using signal-date "
        "OHLCV/context. Paper entry is the next available open with production "
        "entry slippage; exit is 20 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
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
        ],
    )
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
        framework.base._repo_rel(OUT_JSON),
        framework.base._repo_rel(LOG_JSON),
        framework.base._repo_rel(TICKET_JSON),
        framework.base._repo_rel(CARD_MD),
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
            "# exp-20260531-005 Full-Universe Alpha-Score Top-1 Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper source admits the liquid stock with the highest PIT full-universe alpha_score each signal day, top-1 per day, next-open entry, 20-trading-day exit.",
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
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result is not promoted without a shared default-off adapter and parity tests.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Full-universe alpha-score top-1 candidate pool",
        "status": payload["status"],
        "decision": payload["decision"],
        "json": framework.base._repo_rel(OUT_JSON),
        "card": framework.base._repo_rel(CARD_MD),
        "before_aggregate": payload["judge_before_aggregate"],
        "after_aggregate": payload["judge_after_aggregate"],
        "summary": payload["interpretation"],
        "completed_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "failed_reasons": payload["gate4"]["failed_reasons"],
            "result_file": framework.base._repo_rel(OUT_JSON),
            "card_file": framework.base._repo_rel(CARD_MD),
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
    framework.base._write_text(CARD_MD, _build_report(payload))
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
