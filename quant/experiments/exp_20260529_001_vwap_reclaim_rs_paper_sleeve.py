"""exp-20260529-001: VWAP reclaim relative-strength paper sleeve.

This alpha search tests one stock-only, free-OHLCV candidate-pool source:
stocks that reclaim their 20-day volume-weighted average close while showing
positive 20-day relative strength versus SPY. The sleeve is default-off paper
only, admits at most one candidate per signal day, enters at the next available
open, and exits after ten trading days.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260528_037_ticker_accumulation_quality_breakout as framework


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260529-001"
STEM = "vwap_reclaim_rs_paper_sleeve"
TRIAL_FAMILY = "vwap_reclaim_rs_candidate_pool"
CHANGED_VARIABLE = "vwap_reclaim_rs_candidate_source_v1"
RULE_VERSION = "vwap20_reclaim_rs_stock_only_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

VWAP_DAYS = 20
MOVING_AVERAGE_DAYS = 50
RELATIVE_STRENGTH_DAYS = 20
MIN_AVG_DOLLAR_VOLUME = 20_000_000.0
MIN_SIGNAL_CLOSE_LOCATION = 0.60
MIN_RS_20D_VS_SPY = 0.0
MAX_EXTENSION_ABOVE_VWAP = 0.06
MAX_PRIOR_CLOSE_ABOVE_VWAP = 0.01
MIN_CURRENT_CLOSE_ABOVE_VWAP = 0.001


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
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _volume_weighted_average_close(
    rows: list[dict[str, Any]], start_idx: int, end_idx: int
) -> float | None:
    if start_idx < 0 or end_idx >= len(rows) or start_idx > end_idx:
        return None
    total_value = 0.0
    total_volume = 0.0
    for row in rows[start_idx : end_idx + 1]:
        close = framework.ohlcv_helper._value(row, "Close")
        volume = framework.ohlcv_helper._value(row, "Volume")
        if close is None or volume is None or volume <= 0:
            return None
        total_value += float(close) * float(volume)
        total_volume += float(volume)
    if total_volume <= 0:
        return None
    return total_value / total_volume


def _average_dollar_volume(
    rows: list[dict[str, Any]], start_idx: int, end_idx: int
) -> float | None:
    if start_idx < 0 or end_idx >= len(rows) or start_idx > end_idx:
        return None
    values: list[float] = []
    for row in rows[start_idx : end_idx + 1]:
        close = framework.ohlcv_helper._value(row, "Close")
        volume = framework.ohlcv_helper._value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(float(close) * float(volume))
    if not values:
        return None
    return sum(values) / len(values)


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.ohlcv_helper._baseline_entries(before_result)
    dates = [
        date
        for date in framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    spy_rows = framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = framework.ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()

    min_idx = max(MOVING_AVERAGE_DAYS, VWAP_DAYS + 1, RELATIVE_STRENGTH_DAYS)
    for ticker in sorted(set(universe).intersection(snapshot).difference(framework.EXCLUDED_TICKERS)):
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx_by_date = framework.ohlcv_helper._row_index(rows)
        for date in dates:
            idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            if idx is None or spy_idx is None or idx < min_idx or spy_idx < RELATIVE_STRENGTH_DAYS:
                audit["insufficient_history"] += 1
                continue

            close = framework.ohlcv_helper._value(rows[idx], "Close")
            prior_close = framework.ohlcv_helper._value(rows[idx - 1], "Close")
            volume = framework.ohlcv_helper._value(rows[idx], "Volume")
            if not close or not prior_close or not volume:
                audit["missing_close_or_volume"] += 1
                continue

            current_vwap = _volume_weighted_average_close(rows, idx - VWAP_DAYS + 1, idx)
            prior_vwap = _volume_weighted_average_close(rows, idx - VWAP_DAYS, idx - 1)
            avg_dollar_volume = _average_dollar_volume(rows, idx - VWAP_DAYS + 1, idx)
            ma50 = framework._prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
            if not current_vwap or not prior_vwap or not avg_dollar_volume or not ma50:
                audit["missing_vwap_or_trend_context"] += 1
                continue
            if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME:
                audit["low_avg_dollar_volume"] += 1
                continue
            if close <= ma50:
                audit["below_prior_ma50"] += 1
                continue

            prior_close_vs_vwap = (float(prior_close) / prior_vwap) - 1.0
            close_vs_vwap = (float(close) / current_vwap) - 1.0
            if prior_close_vs_vwap > MAX_PRIOR_CLOSE_ABOVE_VWAP:
                audit["prior_close_not_near_or_below_vwap"] += 1
                continue
            if close_vs_vwap < MIN_CURRENT_CLOSE_ABOVE_VWAP:
                audit["current_close_not_reclaiming_vwap"] += 1
                continue
            if close_vs_vwap > MAX_EXTENSION_ABOVE_VWAP:
                audit["too_extended_above_vwap"] += 1
                continue

            signal_close_location = framework._close_location(rows[idx])
            if (
                signal_close_location is None
                or signal_close_location < MIN_SIGNAL_CLOSE_LOCATION
            ):
                audit["weak_signal_close_location"] += 1
                continue

            ret20 = framework._close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
            spy_ret20 = framework._close_return(spy_rows, spy_idx - RELATIVE_STRENGTH_DAYS, spy_idx)
            if ret20 is None or spy_ret20 is None:
                audit["missing_relative_strength"] += 1
                continue
            rs20_vs_spy = ret20 - spy_ret20
            if rs20_vs_spy <= MIN_RS_20D_VS_SPY:
                audit["rs20_not_positive_vs_spy"] += 1
                continue

            ab_entries = entries_by_date.get(date, [])
            candidates.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "strategy": STEM,
                    "rule_version": RULE_VERSION,
                    "close": framework.base._round(close, 4),
                    "prior_close": framework.base._round(prior_close, 4),
                    "volume": framework.base._round(volume, 2),
                    "avg_dollar_volume_20d": framework.base._round(avg_dollar_volume, 2),
                    "ma50": framework.base._round(ma50, 4),
                    "vwap20": framework.base._round(current_vwap, 4),
                    "prior_vwap20": framework.base._round(prior_vwap, 4),
                    "close_vs_vwap20": framework.base._round(close_vs_vwap, 6),
                    "prior_close_vs_vwap20": framework.base._round(prior_close_vs_vwap, 6),
                    "vwap_reclaim_slope": framework.base._round(
                        close_vs_vwap - prior_close_vs_vwap, 6
                    ),
                    "signal_close_location": framework.base._round(signal_close_location, 6),
                    "ret20": framework.base._round(ret20, 6),
                    "spy_ret20": framework.base._round(spy_ret20, 6),
                    "rs20_vs_spy": framework.base._round(rs20_vs_spy, 6),
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
            -float(row["vwap_reclaim_slope"]),
            -float(row["rs20_vs_spy"]),
            -float(row["signal_close_location"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "candidate_count": len(candidates),
        "audit_reject_counts": dict(sorted(audit.items())),
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_vwap_reclaim_rs_paper_sleeve"
        if gate4["passed"]
        else "rejected_vwap_reclaim_rs_paper_sleeve"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.29,
        "expected_ev_delta": 0.15,
        "expected_pnl_delta": 2500.0,
        "main_failure_modes": [
            "nearby_reclaim_family_repeat",
            "thin_sample",
            "late_window_regression",
            "concentration",
        ],
        "confidence_reason": (
            "Meta research favors production-visible candidate-pool alpha, but "
            "recent frozen-window OHLCV candidate-source scouts are noisy."
        ),
        "recorded_at": "2026-05-29T00:07:45+00:00",
        "brier_score": round((0.29 - actual_success) ** 2, 6),
    }

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Stock-only 20-day VWAP reclaim with positive 20-day relative "
                "strength versus SPY may add a cleaner free-OHLCV candidate-pool "
                "replacement source than recent OBV or sector-breadth retreads."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": "vwap_reclaim_rs_v1",
            "prior_trial_count": 5,
            "nearby_prior_experiments": [
                "exp-20260526-004",
                "exp-20260526-011",
                "exp-20260528-018",
                "exp-20260528-022",
                "exp-20260528-037",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "free_ohlcv_vwap_reclaim_relative_strength_candidate_source",
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(framework.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": framework.MAX_PAPER_TRADES_PER_DAY,
                "vwap_days": VWAP_DAYS,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "relative_strength_days": RELATIVE_STRENGTH_DAYS,
                "min_avg_dollar_volume": MIN_AVG_DOLLAR_VOLUME,
                "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
                "min_rs20_vs_spy": MIN_RS_20D_VS_SPY,
                "max_extension_above_vwap": MAX_EXTENSION_ABOVE_VWAP,
                "max_prior_close_above_vwap": MAX_PRIOR_CLOSE_ABOVE_VWAP,
                "min_current_close_above_vwap": MIN_CURRENT_CLOSE_ABOVE_VWAP,
                "source_definition": [
                    "stock ticker only",
                    "prior close not more than 1% above prior 20-day VWAP",
                    "signal close at least 0.1% above current 20-day VWAP",
                    "signal close no more than 6% above current 20-day VWAP",
                    "close above prior 50-day moving average",
                    "signal-day close location >= 0.60",
                    "20-day return exceeds SPY",
                    "20-day average dollar volume >= 20 million",
                ],
                "selection_rank": [
                    "signal_date",
                    "vwap_reclaim_slope desc",
                    "rs20_vs_spy desc",
                    "signal_close_location desc",
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
                    "candidate_pool / entry: stocks reclaiming a 20-day volume-"
                    "weighted cost basis while outperforming SPY may identify "
                    "higher-quality replacement candidates than recent price/OBV "
                    "breakouts."
                ),
                "2_history_check": {
                    "exp-20260526-004_and_011": (
                        "Prior undercut/pullback reclaim sleeves tested price "
                        "reclaim mechanics and QQQ confirmation. This run uses "
                        "ticker-level VWAP cost-basis reclaim with SPY-relative "
                        "strength, not another QQQ confirmation retune."
                    ),
                    "exp-20260528-018_and_022": (
                        "VBB support scouts used market breadth/high-close context. "
                        "This run is a separate stock-level candidate source."
                    ),
                    "exp-20260528-037": (
                        "OBV plus price-breakout failed Gate 4. This run does not "
                        "retune OBV or prior-high breakout thresholds."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                    "3/3 EV-improved windows; no PnL-regressed window; >=20 paper "
                    "trades across all 3 windows; drawdown drift <=0.5pp; survival "
                    ">=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260529_001_vwap_reclaim_rs_paper_sleeve.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay coverage remains sparse; "
                "skipped Companyfacts scalar retunes because the playbook asks for "
                "forward rows; skipped VCP/VBB/state-surface thresholds because "
                "those families need forward evidence or a >10% state-surface gate. "
                "This tests one new free-OHLCV stock-level candidate source."
            ),
            "interpretation": (
                "The VWAP reclaim relative-strength sleeve cleared Gate 4 as a "
                "replay-only lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The VWAP reclaim relative-strength sleeve did not clear Gate 4. "
                    "Do not promote it or retry nearby VWAP/reclaim thresholds on the "
                    "same frozen windows without forward paper rows or a materially "
                    "orthogonal free-data source."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If revisited, use forward replacement-value rows or a materially "
                "new free-data context such as official short-interest/ownership "
                "or filing-timing fields; do not just retune VWAP distance thresholds."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only OHLCV known after the signal-date close; paper entry is "
        "the next available open with production entry slippage; exit is ten "
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
            "vwap20",
            "prior_vwap20",
            "close_vs_vwap20",
            "prior_close_vs_vwap20",
            "vwap_reclaim_slope",
            "signal_close_location",
            "rs20_vs_spy",
        ],
    )
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
    title = "# exp-20260529-001 VWAP Reclaim Relative-Strength Paper Sleeve"
    return "\n".join(
        [
            title,
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper source admits stock-only 20-day VWAP reclaim candidates with positive 20-day relative strength versus SPY, top-1 per day, next-open entry, ten-trading-day exit.",
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
        "title": "VWAP reclaim relative-strength paper sleeve",
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
