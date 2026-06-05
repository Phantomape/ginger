"""exp-20260605-029: estimate revision persistence underreaction scout.

Lane: alpha_search.
Single causal variable:
persistent_positive_estimate_revision_underreaction_candidate_source_v1.

This replay-only/default-off candidate-pool experiment tests whether stocks
with persistent positive EPS-estimate revisions over 10 and 20 trading
earnings snapshots, but without a large 20-day price response versus SPY, have
cleaner 10-day continuation value than the raw revision-velocity scout.

Core signals, ranking, sizing, exits, LLM/news, watchlists, shared adapters,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260604_023_sec_ftd_pressure_breakout_candidate_pool as ftd_base
import exp_20260604_029_analyst_revision_velocity_candidate_pool as revision_base


EXPERIMENT_ID = "exp-20260605-029"
STEM = "estimate_revision_persistence_underreaction"
TRIAL_FAMILY = "estimate_revision_persistence_underreaction_candidate_pool"
CHANGED_VARIABLE = "persistent_positive_estimate_revision_underreaction_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

BASE_NOTIONAL_USD = revision_base.BASE_NOTIONAL_USD
HOLD_DAYS = revision_base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = revision_base.MAX_PAPER_TRADES_PER_DAY

MIN_PRICE = revision_base.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20 = revision_base.MIN_AVG_DOLLAR_VOLUME_20
MIN_VOLUME_RATIO_20 = 0.80
MIN_CLOSE_LOCATION = 0.45
MIN_RET5_EXCESS_SPY = -0.03
MIN_RET20_EXCESS_SPY = -0.03
MAX_RET20_EXCESS_SPY = 0.08

REVISION_LOOKBACK_SHORT_TRADING_DAYS = 10
REVISION_LOOKBACK_LONG_TRADING_DAYS = 20
MIN_EPS_ESTIMATE_REVISION_10D_PCT = 0.01
MIN_EPS_ESTIMATE_REVISION_20D_PCT = revision_base.MIN_EPS_ESTIMATE_REVISION_20D_PCT
MIN_DAYS_TO_EARNINGS = revision_base.MIN_DAYS_TO_EARNINGS
MAX_DAYS_TO_EARNINGS = revision_base.MAX_DAYS_TO_EARNINGS

MIN_TARGET_TRADES = revision_base.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = revision_base.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = revision_base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = revision_base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = revision_base.MAX_POSITIVE_HHI

ROOT = revision_base.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
PERSISTENCE_ROWS_JSON = OUT_DIR / "revision_persistence_rows_summary.json"
PERSISTENCE_FILES_JSON = OUT_DIR / "revision_persistence_snapshot_files.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

framework = revision_base.framework
_ORIGINAL_BUILD_PAYLOAD = revision_base._ORIGINAL_BUILD_PAYLOAD
_PERSISTENCE_CACHE: dict[str, Any] | None = None


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.MIN_PRICE = MIN_PRICE
    framework.MIN_AVG_DOLLAR_VOLUME_20 = MIN_AVG_DOLLAR_VOLUME_20
    framework.MIN_VOLUME_RATIO_20 = MIN_VOLUME_RATIO_20
    framework.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    framework.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_JSON = BEFORE_JSON
    framework.AFTER_JSON = AFTER_JSON
    framework.LOG_JSON = LOG_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.CARD_MD = CARD_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._artifact = _artifact
    framework._build_payload = _build_payload


def _load_persistence_context(
    universe: set[str],
    frames: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    global _PERSISTENCE_CACHE
    tickers = sorted(
        universe.difference(framework.base.shadow.EXCLUDED_TICKERS).difference(
            {"SPY", "QQQ", "IWM"}
        )
    )
    signal_dates = revision_base._signal_dates(frames)
    cache_key = {"tickers": tickers, "signal_dates": signal_dates}
    if _PERSISTENCE_CACHE is not None and _PERSISTENCE_CACHE.get("cache_key") == cache_key:
        return _PERSISTENCE_CACHE

    all_snapshot_paths = sorted(revision_base.SNAPSHOT_DIR.glob("earnings_snapshot_*.json"))
    all_dates = [
        f"{path.stem[-8:][:4]}-{path.stem[-8:][4:6]}-{path.stem[-8:][6:]}"
        for path in all_snapshot_paths
    ]
    path_by_date = dict(zip(all_dates, all_snapshot_paths))
    snapshot_by_date: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    rows_by_date_ticker: dict[str, dict[str, dict[str, Any]]] = {}
    ticker_set = set(tickers)
    signal_date_set = set(signal_dates)

    for signal_date in signal_dates:
        if signal_date not in path_by_date:
            fallback = revision_base._snapshot_path(signal_date)
            if fallback is not None:
                path_by_date[signal_date] = fallback
                all_dates.append(signal_date)
            else:
                files.append(
                    {
                        "date": signal_date,
                        "status": "missing_signal_snapshot",
                        "matched_revision_rows": 0,
                    }
                )
    all_dates = sorted(set(all_dates))
    date_pos = {date: pos for pos, date in enumerate(all_dates)}

    for signal_date in signal_dates:
        pos = date_pos.get(signal_date)
        if pos is None or pos < REVISION_LOOKBACK_LONG_TRADING_DAYS:
            files.append(
                {
                    "date": signal_date,
                    "status": "missing_prior_snapshot_window",
                    "matched_revision_rows": 0,
                }
            )
            continue

        prior_short_date = all_dates[pos - REVISION_LOOKBACK_SHORT_TRADING_DAYS]
        prior_long_date = all_dates[pos - REVISION_LOOKBACK_LONG_TRADING_DAYS]
        signal_path = path_by_date.get(signal_date) or revision_base._snapshot_path(signal_date)
        prior_short_path = path_by_date.get(prior_short_date) or revision_base._snapshot_path(
            prior_short_date
        )
        prior_long_path = path_by_date.get(prior_long_date) or revision_base._snapshot_path(
            prior_long_date
        )
        if signal_path is None or prior_short_path is None or prior_long_path is None:
            files.append(
                {
                    "date": signal_date,
                    "prior_short_date": prior_short_date,
                    "prior_long_date": prior_long_date,
                    "status": "missing_snapshot_file",
                    "matched_revision_rows": 0,
                }
            )
            continue

        current = snapshot_by_date.setdefault(signal_date, revision_base._load_snapshot(signal_path))
        prior_short = snapshot_by_date.setdefault(
            prior_short_date,
            revision_base._load_snapshot(prior_short_path),
        )
        prior_long = snapshot_by_date.setdefault(
            prior_long_date,
            revision_base._load_snapshot(prior_long_path),
        )
        valid_rows = 0
        qualified_rows = 0
        for ticker, current_row in current.items():
            ticker = str(ticker).upper()
            if ticker not in ticker_set:
                continue
            short_row = prior_short.get(ticker)
            long_row = prior_long.get(ticker)
            if not short_row or not long_row:
                continue
            current_estimate = revision_base._float(current_row.get("eps_estimate"))
            short_estimate = revision_base._float(short_row.get("eps_estimate"))
            long_estimate = revision_base._float(long_row.get("eps_estimate"))
            days_to_earnings = revision_base._float(current_row.get("days_to_earnings"))
            if (
                current_estimate is None
                or short_estimate is None
                or long_estimate is None
                or days_to_earnings is None
                or current_estimate <= 0
                or short_estimate <= 0
                or long_estimate <= 0
            ):
                continue
            revision_short = (current_estimate - short_estimate) / abs(short_estimate)
            revision_long = (current_estimate - long_estimate) / abs(long_estimate)
            if not math.isfinite(revision_short) or not math.isfinite(revision_long):
                continue
            monotonic_positive = current_estimate >= short_estimate >= long_estimate
            valid_rows += 1
            avg_surprise = revision_base._float(current_row.get("avg_historical_surprise_pct"))
            surprise_history = current_row.get("historical_surprise_pct") or []
            positive_surprises = sum(
                1 for value in surprise_history if (revision_base._float(value) or 0.0) > 0.0
            )
            row = {
                "ticker": ticker,
                "signal_date": signal_date,
                "current_snapshot": framework._repo_rel(signal_path),
                "prior_short_snapshot": framework._repo_rel(prior_short_path),
                "prior_long_snapshot": framework._repo_rel(prior_long_path),
                "prior_short_snapshot_date": prior_short_date,
                "prior_long_snapshot_date": prior_long_date,
                "revision_lookback_short_trading_days": REVISION_LOOKBACK_SHORT_TRADING_DAYS,
                "revision_lookback_long_trading_days": REVISION_LOOKBACK_LONG_TRADING_DAYS,
                "eps_estimate_current": framework._round(current_estimate, 6),
                "eps_estimate_prior_short": framework._round(short_estimate, 6),
                "eps_estimate_prior_long": framework._round(long_estimate, 6),
                "eps_estimate_revision_10d_pct": framework._round(revision_short, 6),
                "eps_estimate_revision_20d_pct": framework._round(revision_long, 6),
                "days_to_earnings": framework._round(days_to_earnings, 2),
                "monotonic_positive_revision": monotonic_positive,
                "avg_historical_surprise_pct": framework._round(avg_surprise, 6),
                "positive_surprise_count": positive_surprises,
                "surprise_history_count": len(surprise_history),
                "source_caveat": (
                    "Daily snapshots are replayable, but historical EPS estimate "
                    "data is proxy-grade until a production PIT provenance adapter "
                    "is added."
                ),
            }
            rows.append(row)
            rows_by_date_ticker.setdefault(signal_date, {})[ticker] = row
            if (
                monotonic_positive
                and revision_short >= MIN_EPS_ESTIMATE_REVISION_10D_PCT
                and revision_long >= MIN_EPS_ESTIMATE_REVISION_20D_PCT
                and MIN_DAYS_TO_EARNINGS <= days_to_earnings <= MAX_DAYS_TO_EARNINGS
            ):
                qualified_rows += 1

        if signal_date in signal_date_set:
            files.append(
                {
                    "date": signal_date,
                    "prior_short_date": prior_short_date,
                    "prior_long_date": prior_long_date,
                    "status": "ok",
                    "snapshot_path": framework._repo_rel(signal_path),
                    "prior_short_snapshot_path": framework._repo_rel(prior_short_path),
                    "prior_long_snapshot_path": framework._repo_rel(prior_long_path),
                    "valid_revision_rows": valid_rows,
                    "matched_revision_rows": qualified_rows,
                }
            )

    _PERSISTENCE_CACHE = {
        "cache_key": cache_key,
        "rows": rows,
        "files": files,
        "rows_by_date_ticker": rows_by_date_ticker,
        "source": "daily earnings snapshots",
        "source_caveat": (
            "Historical snapshots are replayable but EPS estimate provenance is "
            "proxy-grade; positive results must not be promoted before shared "
            "PIT analyst-revision parity exists."
        ),
    }
    return _PERSISTENCE_CACHE


def _revision_rows_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_month: Counter[str] = Counter()
    by_ticker: Counter[str] = Counter()
    qualified_by_month: Counter[str] = Counter()
    for row in rows:
        signal_date = str(row.get("signal_date") or "")
        month = signal_date[:7]
        if month:
            by_month[month] += 1
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker] += 1
        revision_short = revision_base._float(row.get("eps_estimate_revision_10d_pct"))
        revision_long = revision_base._float(row.get("eps_estimate_revision_20d_pct"))
        days_to_earnings = revision_base._float(row.get("days_to_earnings"))
        if (
            bool(row.get("monotonic_positive_revision"))
            and revision_short is not None
            and revision_long is not None
            and days_to_earnings is not None
            and revision_short >= MIN_EPS_ESTIMATE_REVISION_10D_PCT
            and revision_long >= MIN_EPS_ESTIMATE_REVISION_20D_PCT
            and MIN_DAYS_TO_EARNINGS <= days_to_earnings <= MAX_DAYS_TO_EARNINGS
        ):
            qualified_by_month[month] += 1
    return {
        "row_count": len(rows),
        "ticker_count": len(by_ticker),
        "revision_month_counts": dict(sorted(by_month.items())),
        "qualified_revision_month_counts": dict(sorted(qualified_by_month.items())),
        "top_ticker_row_counts": [
            {"ticker": ticker, "row_count": count}
            for ticker, count in by_ticker.most_common(25)
        ],
        "parameters": {
            "revision_lookback_short_trading_days": REVISION_LOOKBACK_SHORT_TRADING_DAYS,
            "revision_lookback_long_trading_days": REVISION_LOOKBACK_LONG_TRADING_DAYS,
            "min_eps_estimate_revision_10d_pct": MIN_EPS_ESTIMATE_REVISION_10D_PCT,
            "min_eps_estimate_revision_20d_pct": MIN_EPS_ESTIMATE_REVISION_20D_PCT,
            "min_days_to_earnings": MIN_DAYS_TO_EARNINGS,
            "max_days_to_earnings": MAX_DAYS_TO_EARNINGS,
        },
        "source_caveat": (
            "Daily earnings snapshots are replayable; historical estimate "
            "values remain proxy-grade until a PIT vendor/provenance adapter is "
            "added."
        ),
    }


def _candidate_rows_for_window(
    frames: dict[str, pd.DataFrame],
    label: str,
    cfg: dict[str, str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spy = ftd_base._prepared_frame(frames["SPY"]) if "SPY" in frames else None
    if spy is None:
        raise RuntimeError("SPY is required for ret20 excess control")

    universe = {ticker.upper() for ticker in frames}
    revision_context = _load_persistence_context(universe, frames)
    rows_by_date_ticker = revision_context["rows_by_date_ticker"]
    core_entries = framework.base.shadow._baseline_entries(before_result)
    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    raw_pass_counts: Counter[str] = Counter()
    reject_counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    start = pd.Timestamp(cfg["start"])
    end = pd.Timestamp(cfg["end"])
    spy_closes = [float(value) for value in spy["Close"].tolist()]

    for ticker, frame in frames.items():
        ticker = ticker.upper()
        if ticker in framework.base.shadow.EXCLUDED_TICKERS or ticker in {"SPY", "QQQ", "IWM"}:
            continue
        fr = ftd_base._prepared_frame(frame)
        closes = [float(value) for value in fr["Close"].tolist()]
        pos_by_date = {idx: pos for pos, idx in enumerate(fr.index)}
        for asof in fr.loc[start:end].index:
            signal_date = str(asof.date())
            revision_row = rows_by_date_ticker.get(signal_date, {}).get(ticker)
            if revision_row is None:
                continue
            raw_pass_counts["snapshot_revision_row"] += 1
            revision_short = revision_base._float(revision_row.get("eps_estimate_revision_10d_pct"))
            revision_long = revision_base._float(revision_row.get("eps_estimate_revision_20d_pct"))
            days_to_earnings = revision_base._float(revision_row.get("days_to_earnings"))
            if revision_short is None or revision_long is None or days_to_earnings is None:
                reject_counts["missing_revision_or_dte"] += 1
                continue
            if not bool(revision_row.get("monotonic_positive_revision")):
                reject_counts["non_monotonic_revision_path"] += 1
                continue
            if revision_short < MIN_EPS_ESTIMATE_REVISION_10D_PCT:
                reject_counts["revision_10d_below_threshold"] += 1
                continue
            if revision_long < MIN_EPS_ESTIMATE_REVISION_20D_PCT:
                reject_counts["revision_20d_below_threshold"] += 1
                continue
            if not (MIN_DAYS_TO_EARNINGS <= days_to_earnings <= MAX_DAYS_TO_EARNINGS):
                reject_counts["days_to_earnings_outside_window"] += 1
                continue
            raw_pass_counts["revision_persistence_passed"] += 1

            pos = pos_by_date[asof]
            if pos + HOLD_DAYS >= len(fr.index) or pos + 1 >= len(fr.index):
                continue
            if asof not in spy.index:
                continue
            row = fr.loc[asof]
            spy_pos = int(spy.index.get_loc(asof))
            ret5 = framework._ret(closes, pos, 5)
            ret20 = framework._ret(closes, pos, 20)
            spy_ret5 = framework._ret(spy_closes, spy_pos, 5)
            spy_ret20 = framework._ret(spy_closes, spy_pos, 20)
            ret5_excess_spy = (
                ret5 - spy_ret5
                if ret5 is not None and spy_ret5 is not None
                else None
            )
            ret20_excess_spy = (
                ret20 - spy_ret20
                if ret20 is not None and spy_ret20 is not None
                else None
            )
            values = {
                "close": float(row["Close"]),
                "avg_dollar_volume_20": float(row["avg_dollar_volume_20"]),
                "volume_ratio_20": float(row["volume_ratio_20"]),
                "close_location": float(row["close_location"]),
                "ret5_excess_spy": ret5_excess_spy,
                "ret20_excess_spy": ret20_excess_spy,
            }
            if any(value is None or not math.isfinite(value) for value in values.values()):
                continue
            raw_pass_counts["fields_non_null"] += 1
            if values["close"] < MIN_PRICE:
                continue
            if values["avg_dollar_volume_20"] < MIN_AVG_DOLLAR_VOLUME_20:
                continue
            raw_pass_counts["liquidity_passed"] += 1
            if values["volume_ratio_20"] < MIN_VOLUME_RATIO_20:
                reject_counts["volume_ratio_below_threshold"] += 1
                continue
            if values["close_location"] < MIN_CLOSE_LOCATION:
                reject_counts["close_location_below_threshold"] += 1
                continue
            if values["ret5_excess_spy"] < MIN_RET5_EXCESS_SPY:
                reject_counts["ret5_excess_too_weak"] += 1
                continue
            if values["ret20_excess_spy"] < MIN_RET20_EXCESS_SPY:
                reject_counts["ret20_excess_too_weak"] += 1
                continue
            if values["ret20_excess_spy"] > MAX_RET20_EXCESS_SPY:
                reject_counts["ret20_excess_already_expanded"] += 1
                continue
            raw_pass_counts["underreaction_price_action_passed"] += 1

            same_day_core = core_entries.get(signal_date, [])
            if any(str(entry.get("ticker") or "").upper() == ticker for entry in same_day_core):
                reject_counts["same_day_core_ticker_overlap"] += 1
                continue
            underreaction_bonus = MAX_RET20_EXCESS_SPY - values["ret20_excess_spy"]
            score = (
                min(revision_long, 0.50) * 9.0
                + min(revision_short, 0.25) * 7.0
                + max(underreaction_bonus, 0.0) * 1.5
                + values["close_location"] * 0.5
                + min(values["volume_ratio_20"], 3.0) * 0.15
            )
            candidate = {
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "window": label,
                "score": framework._round(score, 6),
                "prior_short_snapshot_date": revision_row.get("prior_short_snapshot_date"),
                "prior_long_snapshot_date": revision_row.get("prior_long_snapshot_date"),
                "eps_estimate_current": revision_row.get("eps_estimate_current"),
                "eps_estimate_prior_short": revision_row.get("eps_estimate_prior_short"),
                "eps_estimate_prior_long": revision_row.get("eps_estimate_prior_long"),
                "eps_estimate_revision_10d_pct": framework._round(revision_short, 6),
                "eps_estimate_revision_20d_pct": framework._round(revision_long, 6),
                "days_to_earnings": framework._round(days_to_earnings, 2),
                "avg_historical_surprise_pct": revision_row.get("avg_historical_surprise_pct"),
                "positive_surprise_count": revision_row.get("positive_surprise_count"),
                "surprise_history_count": revision_row.get("surprise_history_count"),
                "avg_dollar_volume_20": framework._round(values["avg_dollar_volume_20"], 2),
                "volume_ratio_20": framework._round(values["volume_ratio_20"], 6),
                "close_location": framework._round(values["close_location"], 6),
                "ret5_excess_spy": framework._round(values["ret5_excess_spy"], 6),
                "ret20_excess_spy": framework._round(values["ret20_excess_spy"], 6),
                "same_day_core_entry_count": len(same_day_core),
                "same_ticker_core_overlap": False,
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_orders": False,
                "source_caveat": revision_row.get("source_caveat"),
            }
            if len(examples) < 20:
                examples.append(
                    {
                        "ticker": ticker,
                        "date": signal_date,
                        "revision_10d": candidate["eps_estimate_revision_10d_pct"],
                        "revision_20d": candidate["eps_estimate_revision_20d_pct"],
                        "ret20_excess_spy": candidate["ret20_excess_spy"],
                        "days_to_earnings": candidate["days_to_earnings"],
                    }
                )
            candidates_by_date.setdefault(signal_date, []).append(candidate)

    selected: list[dict[str, Any]] = []
    raw_candidate_count = 0
    for signal_date, rows in sorted(candidates_by_date.items()):
        raw_candidate_count += len(rows)
        rows.sort(
            key=lambda item: (
                -float(item["score"]),
                -float(item["eps_estimate_revision_20d_pct"]),
                float(item["ret20_excess_spy"]),
                item["ticker"],
            )
        )
        selected.extend(rows[:MAX_PAPER_TRADES_PER_DAY])

    return selected, {
        "raw_pass_counts": dict(raw_pass_counts),
        "revision_reject_counts": dict(sorted(reject_counts.items())),
        "revision_examples": examples,
        "raw_candidate_count": raw_candidate_count,
        "candidate_day_count": len(candidates_by_date),
    }


def _build_payload() -> dict[str, Any]:
    _patch_framework()
    payload = _ORIGINAL_BUILD_PAYLOAD()
    revision_context = _PERSISTENCE_CACHE or {}
    framework._write_json(
        PERSISTENCE_ROWS_JSON,
        _revision_rows_summary(revision_context.get("rows", [])),
    )
    framework._write_json(PERSISTENCE_FILES_JSON, revision_context.get("files", []))

    numeric_passed = bool(payload["gate4"]["passed"])
    promotable_source = False
    passed = numeric_passed and promotable_source
    if numeric_passed:
        decision = "positive_proxy_lead_not_retained_requires_pit_revision_source"
        rationale = (
            "Numeric Gate 4 passed, but the historical EPS-estimate snapshot "
            "source is proxy-grade. Do not retain or promote until a shared "
            "PIT analyst-revision adapter proves production/backtest parity."
        )
    else:
        decision = "rejected_estimate_revision_persistence_underreaction"
        rationale = "Gate 4 failed; no production or shared policy behavior is retained."

    actual_success = 1 if passed else 0
    ev_delta = payload["aggregate"]["expected_value_score_delta_sum"]
    pnl_delta = payload["aggregate"]["total_pnl_delta_sum"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": decision,
            "decision": decision,
            "accepted": passed,
            "hypothesis": (
                "Persistent positive EPS estimate revision over both 10 and 20 "
                "trading earnings snapshots, combined with liquid underreacted "
                "price action, may identify cleaner default-off paper "
                "candidates than raw revision velocity."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": CHANGED_VARIABLE,
            "mechanism_family": "analyst_revision_expectation_trajectory",
            "prior_trial_count": 5,
            "nearby_prior_experiments": [
                "exp-20260531-001",
                "exp-20260531-003",
                "exp-20260604-001",
                "exp-20260602-023",
                "exp-20260604-029",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "daily_earnings_snapshot_revision_persistence_underreaction",
            "interpretation": rationale,
            "rejection_reason": None if numeric_passed else "; ".join(payload["gate4"]["failed_gates"]),
            "prediction": {
                "success_probability": 0.18,
                "expected_ev_delta": 0.18,
                "expected_pnl_delta": 2500.0,
                "main_failure_modes": [
                    "old_thin_regression",
                    "proxy_revision_source_noise",
                    "thin_sample",
                    "positive_pnl_concentration",
                ],
                "confidence_reason": (
                    "Raw revision velocity improved aggregate EV but failed "
                    "one window; persistence plus underreaction directly "
                    "targets that failure while remaining proxy-grade."
                ),
                "recorded_at": "2026-06-05T18:08:57+00:00",
                "actual_success": actual_success,
                "actual_ev_delta": ev_delta,
                "actual_pnl_delta": pnl_delta,
                "brier_score": round((0.18 - actual_success) ** 2, 6),
            },
            "earnings_revision_source": {
                "source": revision_context.get("source"),
                "row_count": len(revision_context.get("rows", [])),
                "file_count": len(revision_context.get("files", [])),
                "rows_artifact": framework._repo_rel(PERSISTENCE_ROWS_JSON),
                "files_artifact": framework._repo_rel(PERSISTENCE_FILES_JSON),
                "source_caveat": revision_context.get("source_caveat"),
            },
        }
    )
    payload["parameters"].update(
        {
            "single_changed_variable": CHANGED_VARIABLE,
            "source_relation": (
                "Ticker must have positive monotonic EPS estimate revisions "
                "over 10 and 20 trading earnings snapshots, days_to_earnings "
                "between 7 and 60, liquid OHLCV, and underreacted price action "
                "with 20d excess return versus SPY between -3% and +8%."
            ),
            "revision_lookback_short_trading_days": REVISION_LOOKBACK_SHORT_TRADING_DAYS,
            "revision_lookback_long_trading_days": REVISION_LOOKBACK_LONG_TRADING_DAYS,
            "min_eps_estimate_revision_10d_pct": MIN_EPS_ESTIMATE_REVISION_10D_PCT,
            "min_eps_estimate_revision_20d_pct": MIN_EPS_ESTIMATE_REVISION_20D_PCT,
            "min_days_to_earnings": MIN_DAYS_TO_EARNINGS,
            "max_days_to_earnings": MAX_DAYS_TO_EARNINGS,
            "min_ret5_excess_spy": MIN_RET5_EXCESS_SPY,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "max_ret20_excess_spy": MAX_RET20_EXCESS_SPY,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry / candidate_pool: persistent analyst estimate upgrades "
            "should create drift only when price has not already fully "
            "expanded against SPY."
        ),
        "2_history_check": {
            "exp-20260604-029": (
                "Raw 20d revision velocity improved aggregate EV/PnL but "
                "failed old_thin EV/PnL. This run keeps the 20d threshold and "
                "changes the classifier to require 10d persistence plus an "
                "underreaction price band."
            ),
            "exp-20260531-001": (
                "Pre-earnings surprise/revision/RS was negative; this run does "
                "not chase imminent earnings and keeps 7-60 days to event."
            ),
            "exp-20260602-023": (
                "Accepted post-earnings drift is a separate after-event PEAD "
                "source; this is a pre-event default-off candidate pool."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three windows; positive aggregate "
            "EV/PnL; no EV/PnL-regressed window; sample, drawdown, survival, "
            "and concentration guards pass; source provenance must be shared "
            "and parity-safe before promotion."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260605_029_estimate_revision_persistence_underreaction.py"
        ),
    }
    payload["gate2"].update(
        {
            "minimum_open_position_fields_checked": ["entry_date", "target_price"],
            "earnings_snapshot_required_fields": [
                "eps_estimate",
                "days_to_earnings",
                "historical_surprise_pct",
            ],
            "llm_dependency": False,
        }
    )
    payload["production_impact"].update(
        {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_data_fetch_changed": False,
            "requires_shared_adapter_before_promotion": numeric_passed,
        }
    )
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "source_provenance_promotable": promotable_source,
        "parity_note": (
            "This runner changes no production path. Because historical EPS "
            "estimate snapshots are proxy-grade, even a numeric pass is only "
            "a research lead until a shared PIT analyst-revision source and "
            "backtest/production parity tests exist."
        ),
    }
    payload["next_retry_requires"] = (
        "If rejected, do not retune nearby revision or price-band thresholds "
        "on the frozen sample; valid next work is a PIT analyst-estimate source "
        "with revision persistence/analyst-count trajectory, or forward "
        "replacement rows for this proxy lead."
    )
    payload["related_files"] = [
        framework._repo_rel(Path(__file__)),
        framework._repo_rel(OUT_JSON),
        framework._repo_rel(BEFORE_JSON),
        framework._repo_rel(AFTER_JSON),
        framework._repo_rel(PERSISTENCE_ROWS_JSON),
        framework._repo_rel(PERSISTENCE_FILES_JSON),
        framework._repo_rel(LOG_JSON),
        framework._repo_rel(ARTIFACT_MD),
        framework._repo_rel(CARD_MD),
        framework._repo_rel(EXPERIMENT_LOG),
    ]
    payload["gate4"]["numeric_passed"] = numeric_passed
    payload["gate4"]["passed"] = passed
    payload["gate4"]["decision"] = decision
    payload["gate4"]["rationale"] = rationale
    payload["gate4"]["requires_parity_before_promotion"] = numeric_passed
    payload["gate4"]["source_provenance_guard"] = {
        "promotable_source": promotable_source,
        "reason": "historical EPS estimate snapshots are proxy-grade",
    }
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Estimate Revision Persistence Underreaction",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['baseline_expected_value_score_sum']}` -> "
        f"`{agg['after_expected_value_score_sum']}` "
        f"({agg['expected_value_score_delta_sum']:+.4f})",
        f"- aggregate PnL delta: `${agg['total_pnl_delta_sum']:+,.2f}`",
        f"- target trades: `{target['total_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_pnl_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(gate4['failed_gates']) or 'none'}`",
        f"- numeric Gate 4 passed: `{gate4.get('numeric_passed')}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | target trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"${row['delta']['total_pnl']:+,.2f} | {row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            gate4["rationale"],
            "",
            "The tested fields are daily earnings-snapshot EPS estimates, "
            "same-day/prior OHLCV, and SPY relative strength. The result is "
            "replay-only/default-off: no production entry, ranking, sizing, "
            "exit, LLM/news, watchlist, or order behavior changed.",
            "",
            "## Top Positive Contributors",
            "",
            "| ticker | trades | paper PnL | positive PnL share |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in target["ticker_rows"][:10]:
        lines.append(
            f"| {row['ticker']} | {row['trade_count']} | "
            f"${row['paper_pnl_usd']:+,.2f} | {row['positive_pnl_share']} |"
        )
    return "\n".join(lines) + "\n"


def run(output: Path = OUT_JSON) -> dict[str, Any]:
    _patch_framework()
    return framework.run(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    t0 = time.time()
    payload = run(args.output)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "runtime_seconds": round(time.time() - t0, 1),
                "aggregate": payload["aggregate"],
                "gate4": payload["gate4"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "total_trade_count",
                        "total_pnl",
                        "by_window_pnl",
                        "max_single_positive_pnl_share",
                        "positive_pnl_hhi",
                    )
                },
                "artifact": framework._repo_rel(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
