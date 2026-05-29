"""exp-20260529-013: residual-leadership pullback candidate pool.

This alpha search tests one free-OHLCV, stock-only candidate-pool source. It
admits liquid stocks that remain strong 60-day residual leaders versus SPY,
pull back over five days while staying above the 50-day trend, and only fires
when QQQ 20-day momentum is leading SPY. Core signals, ranking, sizing, exits,
LLM/news replay, watchlists, and live/default orders are unchanged.

No JavaScript is used.
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

EXPERIMENT_ID = "exp-20260529-013"
STEM = "residual_leadership_pullback_candidate_pool"
TRIAL_FAMILY = "residual_leadership_pullback_candidate_pool"
CHANGED_VARIABLE = "residual_leadership_pullback_candidate_source_v1"
RULE_VERSION = "residual_leadership_pullback_rank_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260529_013_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_CLOSE = 5.0
MIN_AVG_DOLLAR_VOLUME_20D = 40_000_000.0
MOVING_AVERAGE_DAYS = 50
RELATIVE_STRENGTH_DAYS = 60
MARKET_CONFIRM_DAYS = 20
PULLBACK_DAYS = 5
MIN_RET60_VS_SPY = 0.05
MIN_RET20 = 0.0
MIN_QQQ_RET20_MINUS_SPY = 0.0
MIN_RET5 = -0.08
MAX_RET5 = 0.02
MIN_SIGNAL_CLOSE_LOCATION = 0.35
MAX_DRAWDOWN_FROM_60D_HIGH = -0.18

MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

EXCLUDED_TICKERS = framework.EXCLUDED_TICKERS


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
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _avg_dollar_volume(
    rows: list[dict[str, Any]],
    idx: int,
    days: int,
) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for row in rows[idx - days:idx]:
        close = framework.ohlcv_helper._value(row, "Close")
        volume = framework.ohlcv_helper._value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(float(close) * float(volume))
    return sum(values) / len(values) if values else None


def _prior_high(
    rows: list[dict[str, Any]],
    idx: int,
    days: int,
) -> float | None:
    if idx < days:
        return None
    values = [
        framework.ohlcv_helper._value(row, "High")
        for row in rows[idx - days:idx]
    ]
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return max(clean)


def _signal_day_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prior_close = framework.ohlcv_helper._value(rows[idx - 1], "Close")
    close = framework.ohlcv_helper._value(rows[idx], "Close")
    if not prior_close or close is None:
        return None
    return (float(close) / float(prior_close)) - 1.0


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
    qqq_rows = framework.ohlcv_helper._series(snapshot, "QQQ")
    spy_index = framework.ohlcv_helper._row_index(spy_rows)
    qqq_index = framework.ohlcv_helper._row_index(qqq_rows)
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    min_idx = max(
        MOVING_AVERAGE_DAYS,
        RELATIVE_STRENGTH_DAYS,
        MARKET_CONFIRM_DAYS,
        PULLBACK_DAYS,
    )

    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx_by_date = framework.ohlcv_helper._row_index(rows)
        for date in dates:
            idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            qqq_idx = qqq_index.get(date)
            if (
                idx is None
                or spy_idx is None
                or qqq_idx is None
                or idx < min_idx
                or spy_idx < RELATIVE_STRENGTH_DAYS
                or qqq_idx < MARKET_CONFIRM_DAYS
            ):
                audit["insufficient_history"] += 1
                continue

            close = framework.ohlcv_helper._value(rows[idx], "Close")
            volume = framework.ohlcv_helper._value(rows[idx], "Volume")
            if close is None or volume is None or float(close) < MIN_CLOSE:
                audit["missing_or_low_price_volume"] += 1
                continue

            avg_dollar_volume = _avg_dollar_volume(rows, idx, 20)
            if (
                avg_dollar_volume is None
                or avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D
            ):
                audit["low_avg_dollar_volume"] += 1
                continue

            ma50 = framework._prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
            if ma50 is None or float(close) <= float(ma50):
                audit["below_50d_trend"] += 1
                continue

            ret60 = framework._close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
            spy_ret60 = framework._close_return(
                spy_rows,
                spy_idx - RELATIVE_STRENGTH_DAYS,
                spy_idx,
            )
            if ret60 is None or spy_ret60 is None:
                audit["missing_ret60"] += 1
                continue
            ret60_vs_spy = ret60 - spy_ret60
            if ret60_vs_spy < MIN_RET60_VS_SPY:
                audit["weak_residual_leadership"] += 1
                continue

            ret20 = framework._close_return(rows, idx - MARKET_CONFIRM_DAYS, idx)
            spy_ret20 = framework._close_return(
                spy_rows,
                spy_idx - MARKET_CONFIRM_DAYS,
                spy_idx,
            )
            qqq_ret20 = framework._close_return(
                qqq_rows,
                qqq_idx - MARKET_CONFIRM_DAYS,
                qqq_idx,
            )
            if ret20 is None or spy_ret20 is None or qqq_ret20 is None:
                audit["missing_ret20_or_market_context"] += 1
                continue
            qqq_minus_spy_ret20 = qqq_ret20 - spy_ret20
            if qqq_minus_spy_ret20 <= MIN_QQQ_RET20_MINUS_SPY:
                audit["qqq_not_leading_spy"] += 1
                continue
            if ret20 < MIN_RET20:
                audit["negative_20d_momentum"] += 1
                continue

            ret5 = framework._close_return(rows, idx - PULLBACK_DAYS, idx)
            if ret5 is None:
                audit["missing_ret5"] += 1
                continue
            if ret5 < MIN_RET5 or ret5 > MAX_RET5:
                audit["not_controlled_pullback"] += 1
                continue

            prior_high_60d = _prior_high(rows, idx, RELATIVE_STRENGTH_DAYS)
            if not prior_high_60d:
                audit["missing_prior_high"] += 1
                continue
            drawdown_from_60d_high = (float(close) / prior_high_60d) - 1.0
            if drawdown_from_60d_high < MAX_DRAWDOWN_FROM_60D_HIGH:
                audit["too_far_from_60d_high"] += 1
                continue

            signal_close_location = framework._close_location(rows[idx])
            if (
                signal_close_location is None
                or signal_close_location < MIN_SIGNAL_CLOSE_LOCATION
            ):
                audit["weak_signal_close_location"] += 1
                continue

            signal_return_1d = _signal_day_return(rows, idx)
            if signal_return_1d is None or signal_return_1d < MIN_RET5:
                audit["signal_day_damage"] += 1
                continue

            same_day_entries = entries_by_date.get(date, [])
            pullback_depth = max(-ret5, 0.0)
            residual_leadership_score = (
                max(ret60_vs_spy, 0.0) * 4.0
                + max(ret20 - spy_ret20, 0.0) * 1.5
                + pullback_depth * 1.25
                + max(qqq_minus_spy_ret20, 0.0)
                + signal_close_location * 0.10
            )
            candidates.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "strategy": STEM,
                    "rule_version": RULE_VERSION,
                    "close": framework.base._round(close, 4),
                    "volume": framework.base._round(volume, 2),
                    "avg_dollar_volume_20d": framework.base._round(
                        avg_dollar_volume,
                        2,
                    ),
                    "ma50": framework.base._round(ma50, 4),
                    "ret60": framework.base._round(ret60, 6),
                    "spy_ret60": framework.base._round(spy_ret60, 6),
                    "ret60_vs_spy": framework.base._round(ret60_vs_spy, 6),
                    "ret20": framework.base._round(ret20, 6),
                    "spy_ret20": framework.base._round(spy_ret20, 6),
                    "ret20_vs_spy": framework.base._round(ret20 - spy_ret20, 6),
                    "qqq_ret20": framework.base._round(qqq_ret20, 6),
                    "qqq_minus_spy_ret20": framework.base._round(
                        qqq_minus_spy_ret20,
                        6,
                    ),
                    "ret5": framework.base._round(ret5, 6),
                    "pullback_depth_5d": framework.base._round(pullback_depth, 6),
                    "prior_high_60d": framework.base._round(prior_high_60d, 4),
                    "drawdown_from_60d_high": framework.base._round(
                        drawdown_from_60d_high,
                        6,
                    ),
                    "signal_day_return_1d": framework.base._round(
                        signal_return_1d,
                        6,
                    ),
                    "signal_close_location": framework.base._round(
                        signal_close_location,
                        6,
                    ),
                    "residual_leadership_score": framework.base._round(
                        residual_leadership_score,
                        6,
                    ),
                    "same_day_ab_entry_count": len(same_day_entries),
                    "same_day_ab_overlap": bool(same_day_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in same_day_entries
                    ),
                    "known_at": "after_signal_date_close_before_next_open_paper_entry",
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["residual_leadership_score"]),
            -float(row["ret60_vs_spy"]),
            -float(row["pullback_depth_5d"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "candidate_count": len(candidates),
        "audit_reject_counts": dict(sorted(audit.items())),
    }


def _field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    return framework._field_coverage(rows, fields)


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_residual_leadership_pullback_pool"
        if gate4["passed"]
        else "rejected_residual_leadership_pullback_pool"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.28,
        "expected_ev_delta": 0.35,
        "expected_pnl_delta": 7000.0,
        "main_failure_modes": [
            "drawdown_drift",
            "pattern_ohlcv_overfit",
            "late_strong_regression",
            "concentration",
        ],
        "confidence_reason": (
            "Old pullback/RS research had standalone rank signal and the "
            "QQQ-confirmed pullback paper sleeve improved EV/PnL in all "
            "windows, but failed drawdown. This stricter source tests residual "
            "leadership rather than a broad pullback pattern."
        ),
        "recorded_at": "2026-05-29T11:11:44+00:00",
        "brier_score": round((0.28 - actual_success) ** 2, 6),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "EOD residual-leadership pullback candidates may add stock-only "
                "paper alpha by selecting liquid names whose 60-day excess "
                "leadership remains intact after a controlled five-day pause, "
                "but only when QQQ leads SPY."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": "residual_leadership_pullback_rank_v1",
            "prior_trial_count": 3,
            "nearby_prior_experiments": [
                "exp-20260503-008",
                "exp-20260506-019",
                "exp-20260526-011",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "free_ohlcv_cross_sectional_residual_leadership_candidate_source"
            ),
            "prediction": prediction,
            "backtest_protocol": {
                "source": "docs/backtesting.md canonical three-window replay",
                "windows": framework.base.WINDOWS,
                "replay_llm": False,
                "replay_news": False,
                "REGIME_AWARE_EXIT": True,
                "execution_model": (
                    "Signal uses only OHLCV known after the signal-date close; "
                    "paper entry is the next available open with production "
                    "entry slippage; exit is ten trading days after the signal "
                    "with target-side sell slippage and ROUND_TRIP_COST_PCT."
                ),
            },
            "parameters": {
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "min_close": MIN_CLOSE,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "relative_strength_days": RELATIVE_STRENGTH_DAYS,
                "market_confirm_days": MARKET_CONFIRM_DAYS,
                "pullback_days": PULLBACK_DAYS,
                "min_ret60_vs_spy": MIN_RET60_VS_SPY,
                "min_ret20": MIN_RET20,
                "min_qqq_ret20_minus_spy": MIN_QQQ_RET20_MINUS_SPY,
                "min_ret5": MIN_RET5,
                "max_ret5": MAX_RET5,
                "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
                "max_drawdown_from_60d_high": MAX_DRAWDOWN_FROM_60D_HIGH,
                "stock_excluded_tickers": sorted(EXCLUDED_TICKERS),
                "source_definition": [
                    "stock ticker only",
                    "average dollar volume 20d >= 40 million",
                    "close above 50-day moving average",
                    "60-day return exceeds SPY by at least 5 percentage points",
                    "20-day stock return nonnegative",
                    "QQQ 20-day return exceeds SPY 20-day return",
                    "5-day return between -8% and +2%",
                    "drawdown from prior 60-day high no worse than -18%",
                    "signal close location >= 0.35",
                ],
                "selection_rank": [
                    "signal_date",
                    "residual_leadership_score desc",
                    "ret60_vs_spy desc",
                    "pullback_depth_5d desc",
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
                "acceptance": {
                    "aggregate_ev_delta_gt": 0,
                    "aggregate_pnl_delta_gt": 0,
                    "ev_improved_windows": 3,
                    "max_ev_regressed_windows": 0,
                    "max_pnl_regressed_windows": 0,
                    "min_target_trades": MIN_TARGET_TRADES,
                    "min_target_windows": MIN_TARGET_WINDOWS,
                    "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                    "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                    "max_positive_hhi": MAX_POSITIVE_HHI,
                },
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: residual leaders that pause without "
                    "breaking trend may have cleaner continuation value than "
                    "generic breakout or broad pullback rules."
                ),
                "2_history_check": {
                    "exp-20260503-008": (
                        "Observed-only cross-sectional pullback/RS research "
                        "showed standalone rank information but lacked a "
                        "slot-aware three-window overlay."
                    ),
                    "exp-20260506-019": (
                        "Collision-only core candidate ranking by pullback/60d "
                        "momentum failed; this run is additive default-off "
                        "paper, not core collision ranking."
                    ),
                    "exp-20260526-011": (
                        "QQQ-confirmed pullback-reclaim paper improved all three "
                        "EV/PnL windows but failed drawdown. This run tests a "
                        "different residual-leadership source and keeps the "
                        "drawdown guard."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate "
                    "EV/PnL; 3/3 EV and PnL improved; no regression window; "
                    ">=30 paper trades across all 3 windows; drawdown drift "
                    "<=0.5pp; survival >=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260529_013_residual_leadership_pullback_candidate_pool.py"
                ),
            },
            "expected_value_score_delta": payload["delta_metrics"]["aggregate"][
                "expected_value_score_delta_sum"
            ],
            "total_pnl_delta": payload["delta_metrics"]["aggregate"][
                "total_pnl_delta_sum"
            ],
            "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
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
                    "A retained result would still require a shared default-off "
                    "paper adapter plus parity tests before any daily report, "
                    "watchlist, or live/default behavior changes."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking and expectation revision because recent "
                "records show sparse candidate-level coverage. Skipped VBB, VCP, "
                "state-surface, broad-market, Companyfacts, and nearby support "
                "scalar retunes per playbook freeze guidance. This run tests one "
                "free-OHLCV candidate source, not production sizing or exits."
            ),
            "interpretation": (
                "The residual-leadership pullback sleeve cleared Gate 4 as a "
                "replay-only lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The residual-leadership pullback sleeve did not clear Gate 4. "
                    "Do not promote it or retry nearby pullback/RS thresholds on "
                    "the same frozen windows without forward paper rows or an "
                    "orthogonal non-price evidence source."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If revisited, use forward replacement-value rows or a materially "
                "new data source such as PIT expectation-revision depth, SEC text "
                "event quality, or audited institutional-sponsorship data."
            ),
            "related_files": [
                framework.base._repo_rel(Path(__file__)),
                framework.base._repo_rel(OUT_JSON),
                framework.base._repo_rel(BEFORE_AGG_JSON),
                framework.base._repo_rel(AFTER_AGG_JSON),
                framework.base._repo_rel(LOG_JSON),
                framework.base._repo_rel(TICKET_JSON),
                framework.base._repo_rel(DOC_TICKET_JSON),
                framework.base._repo_rel(ARTIFACT_MD),
                framework.base._repo_rel(EXPERIMENT_LOG),
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate2"]["target_trade_field_coverage"] = _field_coverage(
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
            "ret60_vs_spy",
            "ret20_vs_spy",
            "ret5",
            "qqq_minus_spy_ret20",
            "signal_close_location",
            "residual_leadership_score",
        ],
    )
    payload["gate2"]["note"] = (
        "The sleeve uses only same-day and trailing OHLCV fields plus next-open/"
        "exit prices available to the replay. It does not ask LLM or production "
        "to infer hidden fields."
    )
    payload["gate3"] = {
        "new_core_filter_added": False,
        "candidate_pool_changed": False,
        "minimum_core_survival_rate": framework.base._round(
            min(float(row.get("survival_rate") or 0.0) for row in payload["before_metrics"].values()),
            4,
        ),
        "passed": min(float(row.get("survival_rate") or 0.0) for row in payload["before_metrics"].values()) >= 0.05,
        "note": (
            "No core filter or live entry rule was added. The target source is "
            "additive default-off paper, so core survival is unchanged."
        ),
    }
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
            "# exp-20260529-013 Residual-Leadership Pullback Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper source admits stock-only residual-leadership pullback candidates, top-1 per day, next-open entry, ten-trading-day exit.",
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
        "title": "Residual-leadership pullback candidate pool",
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
    payload = _update_payload(framework._build_payload())
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
