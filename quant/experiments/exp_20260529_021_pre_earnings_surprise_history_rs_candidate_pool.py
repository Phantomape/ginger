"""exp-20260529-021: pre-earnings surprise-history RS candidate pool.

This alpha search tests one free, production-visible candidate source: stocks
near an upcoming earnings date with a positive historical surprise tendency and
same-day trend/relative-strength confirmation. The sleeve is default-off paper
only, admits at most one candidate per signal day, enters at the next available
open, and exits after ten trading days.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import exp_20260528_037_ticker_accumulation_quality_breakout as framework


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260529-021"
STEM = "pre_earnings_surprise_history_rs_candidate_pool"
TRIAL_FAMILY = "pre_earnings_surprise_history_rs_candidate_pool"
CHANGED_VARIABLE = "pre_earnings_surprise_history_rs_candidate_source_v1"
RULE_VERSION = "pre_earnings_surprise_history_rs_candidate_source_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260529_021_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_DAYS_TO_EARNINGS = 3
MAX_DAYS_TO_EARNINGS = 12
MIN_AVG_HISTORICAL_SURPRISE_PCT = 3.0
MIN_POSITIVE_SURPRISE_COUNT = 3
MOVING_AVERAGE_DAYS = 50
RELATIVE_STRENGTH_DAYS = 20
AVG_DOLLAR_VOLUME_DAYS = 20
MIN_CLOSE = 5.0
MIN_AVG_DOLLAR_VOLUME_20D = 40_000_000.0
MIN_RS20_VS_SPY = 0.0
MIN_SIGNAL_CLOSE_LOCATION = 0.45
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
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


@lru_cache(maxsize=None)
def _earnings_snapshot_for_date(date: str) -> tuple[dict[str, Any] | None, str | None]:
    yyyymmdd = str(date)[:10].replace("-", "")
    candidates = [
        REPO_ROOT / "data" / "daily" / "snapshots" / "earnings" / f"earnings_snapshot_{yyyymmdd}.json",
        REPO_ROOT / "data" / f"earnings_snapshot_{yyyymmdd}.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            return None, path.name
        earnings = payload.get("earnings") if isinstance(payload, dict) else None
        if isinstance(earnings, dict):
            return earnings, framework.base._repo_rel(path)
    return None, None


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


def _positive_surprise_count(values: Any) -> int:
    if not isinstance(values, list):
        return 0
    count = 0
    for value in values:
        try:
            if float(value) > 0:
                count += 1
        except (TypeError, ValueError):
            continue
    return count


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

    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx_by_date = framework.ohlcv_helper._row_index(rows)
        for date in dates:
            earnings_snapshot, earnings_source = _earnings_snapshot_for_date(date)
            if earnings_snapshot is None:
                audit["missing_earnings_snapshot"] += 1
                continue
            earnings = earnings_snapshot.get(ticker)
            if not isinstance(earnings, dict):
                audit["ticker_missing_from_earnings_snapshot"] += 1
                continue

            try:
                days_to_earnings = float(earnings.get("days_to_earnings"))
            except (TypeError, ValueError):
                audit["missing_days_to_earnings"] += 1
                continue
            if (
                days_to_earnings < MIN_DAYS_TO_EARNINGS
                or days_to_earnings > MAX_DAYS_TO_EARNINGS
            ):
                audit["outside_pre_earnings_window"] += 1
                continue

            try:
                avg_surprise = float(earnings.get("avg_historical_surprise_pct"))
            except (TypeError, ValueError):
                audit["missing_avg_historical_surprise"] += 1
                continue
            surprise_history = earnings.get("historical_surprise_pct") or []
            positive_surprise_count = _positive_surprise_count(surprise_history)
            if (
                avg_surprise < MIN_AVG_HISTORICAL_SURPRISE_PCT
                or positive_surprise_count < MIN_POSITIVE_SURPRISE_COUNT
            ):
                audit["weak_historical_surprise_tendency"] += 1
                continue

            idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            if (
                idx is None
                or spy_idx is None
                or idx < max(MOVING_AVERAGE_DAYS, RELATIVE_STRENGTH_DAYS, AVG_DOLLAR_VOLUME_DAYS)
                or spy_idx < RELATIVE_STRENGTH_DAYS
            ):
                audit["insufficient_ohlcv_history"] += 1
                continue

            close = framework.ohlcv_helper._value(rows[idx], "Close")
            volume = framework.ohlcv_helper._value(rows[idx], "Volume")
            if close is None or volume is None or float(close) < MIN_CLOSE:
                audit["missing_or_low_price_volume"] += 1
                continue

            avg_dollar_volume = _avg_dollar_volume(rows, idx, AVG_DOLLAR_VOLUME_DAYS)
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

            ret20 = framework._close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
            spy_ret20 = framework._close_return(
                spy_rows,
                spy_idx - RELATIVE_STRENGTH_DAYS,
                spy_idx,
            )
            if ret20 is None or spy_ret20 is None:
                audit["missing_relative_strength"] += 1
                continue
            rs20_vs_spy = ret20 - spy_ret20
            if rs20_vs_spy <= MIN_RS20_VS_SPY:
                audit["rs20_not_positive_vs_spy"] += 1
                continue

            signal_close_location = framework._close_location(rows[idx])
            if (
                signal_close_location is None
                or signal_close_location < MIN_SIGNAL_CLOSE_LOCATION
            ):
                audit["weak_signal_close_location"] += 1
                continue

            same_day_entries = entries_by_date.get(date, [])
            days_to_midpoint = abs(
                days_to_earnings
                - ((MIN_DAYS_TO_EARNINGS + MAX_DAYS_TO_EARNINGS) / 2.0)
            )
            pre_earnings_score = (
                avg_surprise * 0.01
                + positive_surprise_count * 0.10
                + max(rs20_vs_spy, 0.0)
                + signal_close_location * 0.05
                - days_to_midpoint * 0.005
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
                    "days_to_earnings": framework.base._round(days_to_earnings, 4),
                    "avg_historical_surprise_pct": framework.base._round(
                        avg_surprise,
                        4,
                    ),
                    "positive_surprise_count": positive_surprise_count,
                    "historical_surprise_pct": surprise_history,
                    "earnings_snapshot_source": earnings_source,
                    "ret20": framework.base._round(ret20, 6),
                    "spy_ret20": framework.base._round(spy_ret20, 6),
                    "rs20_vs_spy": framework.base._round(rs20_vs_spy, 6),
                    "signal_close_location": framework.base._round(
                        signal_close_location,
                        6,
                    ),
                    "pre_earnings_score": framework.base._round(
                        pre_earnings_score,
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
            -float(row["pre_earnings_score"]),
            -float(row["rs20_vs_spy"]),
            -float(row["avg_historical_surprise_pct"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
    }


def _field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    return framework._field_coverage(rows, fields)


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_replay_only_pre_earnings_surprise_history_rs_pool"
        if gate4["passed"]
        else "rejected_pre_earnings_surprise_history_rs_pool"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.28,
        "expected_ev_delta": 0.10,
        "expected_pnl_delta": 2500.0,
        "main_failure_modes": [
            "sample_too_thin",
            "earnings_runup_overfit",
            "window_regression",
        ],
        "confidence_reason": (
            "This is distinct from PEAD/revision tests because it uses "
            "pre-event surprise-history context, but nearby earnings and "
            "expectation families have been weak."
        ),
        "recorded_at": "2026-05-29T17:06:42+00:00",
        "brier_score": round((0.28 - actual_success) ** 2, 6),
    }
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Pre-earnings candidates with positive historical EPS surprise "
                "tendency and same-day RS/trend confirmation may form a "
                "production-visible default-off paper candidate pool."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": "pre_earnings_surprise_history_rs_candidate_source_v1",
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260428-017",
                "exp-20260528-027",
                "exp-20260528-028",
                "exp-20260529-007",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "new_production_visible_free_earnings_snapshot_field"
            ),
            "prediction": prediction,
            "backtest_protocol": {
                "source": "docs/backtesting.md canonical three-window replay",
                "windows": framework.base.WINDOWS,
                "replay_llm": False,
                "replay_news": False,
                "REGIME_AWARE_EXIT": True,
                "execution_model": (
                    "Signal uses only an earnings snapshot and OHLCV known after "
                    "the signal-date close; paper entry is the next available "
                    "open with production entry slippage; exit is ten trading "
                    "days after the signal with target-side sell slippage and "
                    "ROUND_TRIP_COST_PCT."
                ),
            },
            "parameters": {
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "min_days_to_earnings": MIN_DAYS_TO_EARNINGS,
                "max_days_to_earnings": MAX_DAYS_TO_EARNINGS,
                "min_avg_historical_surprise_pct": MIN_AVG_HISTORICAL_SURPRISE_PCT,
                "min_positive_surprise_count": MIN_POSITIVE_SURPRISE_COUNT,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "relative_strength_days": RELATIVE_STRENGTH_DAYS,
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "min_close": MIN_CLOSE,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "min_rs20_vs_spy": MIN_RS20_VS_SPY,
                "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
                "stock_excluded_tickers": sorted(EXCLUDED_TICKERS),
                "source_definition": [
                    "stock ticker only",
                    "earnings snapshot exists for the signal date",
                    "3 <= days_to_earnings <= 12",
                    "avg_historical_surprise_pct >= 3",
                    "at least 3 historical surprise observations are positive",
                    "average dollar volume 20d >= 40 million",
                    "close above 50-day moving average",
                    "20-day return exceeds SPY",
                    "signal-day close location >= 0.45",
                ],
                "selection_rank": [
                    "signal_date",
                    "pre_earnings_score desc",
                    "rs20_vs_spy desc",
                    "avg_historical_surprise_pct desc",
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
                    "candidate_pool / entry: pre-earnings names with repeat "
                    "positive historical surprise and current RS may attract "
                    "positioning before or through the earnings event."
                ),
                "2_history_check": {
                    "exp-20260428-017": (
                        "Observed-only audit on existing A/B candidates used "
                        "near earnings + positive surprise > 0; this run tests "
                        "an additive paper candidate pool with stricter "
                        "surprise-history and RS/trend requirements."
                    ),
                    "exp-20260528-027_and_028": (
                        "PEAD residual/no-residual tests rejected post-earnings "
                        "5d hypotheses. This run is pre-event positioning, not "
                        "a PEAD-window retry."
                    ),
                    "exp-20260529-007": (
                        "Revision magnitude failed as a 5d clue. This run does "
                        "not use estimate revision magnitude."
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
                    "exp_20260529_021_pre_earnings_surprise_history_rs_candidate_pool.py"
                ),
            },
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
                "Skipped LLM soft-ranking because replay-safe attribution remains "
                "sparse; skipped Companyfacts/VBB/VCP/state-surface/Space "
                "threshold retunes per playbook freeze guidance; skipped PEAD "
                "5d retests because recent repaired-field experiments rejected "
                "that horizon. This run tests one pre-event free earnings "
                "snapshot field plus OHLCV confirmation."
            ),
            "interpretation": (
                "The pre-earnings surprise-history RS sleeve cleared Gate 4 as a "
                "replay-only lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The pre-earnings surprise-history RS sleeve did not clear "
                    "Gate 4. Do not promote it or retry nearby earnings-window "
                    "or surprise-history thresholds on these frozen windows "
                    "without forward rows or a materially different pre-event "
                    "field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If revisited, use forward replacement-value rows, a true "
                "multi-season pre-earnings cohort, or a materially different "
                "pre-event expectation field such as revenue estimate velocity "
                "with analyst-count confirmation."
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
            "days_to_earnings",
            "avg_historical_surprise_pct",
            "positive_surprise_count",
            "rs20_vs_spy",
            "signal_close_location",
            "pre_earnings_score",
        ],
    )
    payload["gate2"]["runtime_fields"] = [
        "data/daily/snapshots/earnings/earnings_snapshot_YYYYMMDD.json earnings[ticker].days_to_earnings",
        "data/daily/snapshots/earnings/earnings_snapshot_YYYYMMDD.json earnings[ticker].avg_historical_surprise_pct",
        "data/daily/snapshots/earnings/earnings_snapshot_YYYYMMDD.json earnings[ticker].historical_surprise_pct",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV rows for same-window relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "The sleeve uses only same-day earnings snapshot fields, same-day/trailing "
        "OHLCV fields, and next-open/exit prices available to replay. It does not "
        "ask LLM or production to infer hidden fields."
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
            "# exp-20260529-021 Pre-Earnings Surprise-History RS Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper source admits stock-only pre-earnings surprise-history + RS candidates, top-1 per day, next-open entry, ten-trading-day exit.",
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
        "title": "Pre-earnings surprise-history RS candidate pool",
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
