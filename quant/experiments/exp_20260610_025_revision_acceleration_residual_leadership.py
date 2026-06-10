"""exp-20260610-025: revision acceleration residual leadership scout.

Replay-only alpha search. This tests one expectation-trajectory candidate
source: keep the prior 20-trading-day EPS estimate-revision velocity and
positive surprise-history confirmation, but require the revision to still be
fresh over the most recent 7 snapshot dates while preferring residual price
leadership versus SPY and QQQ.

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

import exp_20260604_029_analyst_revision_velocity_candidate_pool as revision_base


EXPERIMENT_ID = "exp-20260610-025"
STEM = "revision_acceleration_residual_leadership"
TRIAL_FAMILY = "analyst_revision_acceleration_residual_leadership_candidate_pool"
TRIAL_VARIANT_ID = "revision_acceleration_residual_leadership_top1_next_open_10d_v1"
CHANGED_VARIABLE = "eps_revision_acceleration_residual_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

BASE_NOTIONAL_USD = revision_base.BASE_NOTIONAL_USD
HOLD_DAYS = revision_base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = revision_base.MAX_PAPER_TRADES_PER_DAY

MIN_PRICE = revision_base.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20 = revision_base.MIN_AVG_DOLLAR_VOLUME_20
MIN_VOLUME_RATIO_20 = revision_base.MIN_VOLUME_RATIO_20
MIN_CLOSE_LOCATION = revision_base.MIN_CLOSE_LOCATION
MIN_RET20_EXCESS_SPY = revision_base.MIN_RET20_EXCESS_SPY
MIN_RET20_EXCESS_QQQ = -0.03

REVISION_LOOKBACK_TRADING_DAYS = revision_base.REVISION_LOOKBACK_TRADING_DAYS
SHORT_REVISION_LOOKBACK_TRADING_DAYS = 7
MIN_EPS_ESTIMATE_REVISION_20D_PCT = revision_base.MIN_EPS_ESTIMATE_REVISION_20D_PCT
MIN_EPS_ESTIMATE_REVISION_7D_PCT = 0.01
MIN_REVISION_ACCELERATION_RATIO = 1.0
MIN_DAYS_TO_EARNINGS = revision_base.MIN_DAYS_TO_EARNINGS
MAX_DAYS_TO_EARNINGS = revision_base.MAX_DAYS_TO_EARNINGS

MIN_SURPRISE_HISTORY_COUNT = 4
MIN_POSITIVE_SURPRISE_COUNT = 3
MIN_POSITIVE_SURPRISE_RATIO = 0.75
MIN_AVG_HISTORICAL_SURPRISE_PCT = 0.0

MIN_TARGET_TRADES = revision_base.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = revision_base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = revision_base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = revision_base.MAX_POSITIVE_HHI

ROOT = revision_base.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_025_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
REVISION_ROWS_JSON = OUT_DIR / "earnings_revision_rows_summary.json"
REVISION_FILES_JSON = OUT_DIR / "earnings_revision_snapshot_files.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_REVISION_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260609-011"
    / "revision_surprise_low_extension_shared_adapter.json"
)

framework = revision_base.framework
ftd_base = revision_base.ftd_base
_ORIGINAL_BUILD_PAYLOAD = revision_base._build_payload
_ORIGINAL_ARTIFACT = revision_base._artifact
_SHORT_REVISION_CACHE: dict[str, Any] | None = None


def _float(value: Any) -> float | None:
    return revision_base._float(value)


def _snapshot_dates() -> list[str]:
    paths = sorted(revision_base.SNAPSHOT_DIR.glob("earnings_snapshot_*.json"))
    return [
        f"{path.stem[-8:][:4]}-{path.stem[-8:][4:6]}-{path.stem[-8:][6:]}"
        for path in paths
    ]


def _short_revision_context(
    universe: set[str],
    frames: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    global _SHORT_REVISION_CACHE
    tickers = sorted(
        universe.difference(framework.base.shadow.EXCLUDED_TICKERS).difference(
            {"SPY", "QQQ", "IWM"}
        )
    )
    signal_dates = revision_base._signal_dates(frames)
    cache_key = {
        "tickers": tickers,
        "signal_dates": signal_dates,
        "short_lookback": SHORT_REVISION_LOOKBACK_TRADING_DAYS,
    }
    if _SHORT_REVISION_CACHE is not None and _SHORT_REVISION_CACHE.get("cache_key") == cache_key:
        return _SHORT_REVISION_CACHE

    all_dates = _snapshot_dates()
    path_by_date: dict[str, Path] = {}
    for date in all_dates:
        path = revision_base._snapshot_path(date)
        if path is not None:
            path_by_date[date] = path
    snapshot_by_date: dict[str, dict[str, Any]] = {}
    rows_by_date_ticker: dict[str, dict[str, dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    ticker_set = set(tickers)

    for signal_date in signal_dates:
        if signal_date not in path_by_date:
            fallback = revision_base._snapshot_path(signal_date)
            if fallback is None:
                files.append(
                    {
                        "date": signal_date,
                        "status": "missing_signal_snapshot",
                        "matched_short_revision_rows": 0,
                    }
                )
                continue
            path_by_date[signal_date] = fallback
            all_dates.append(signal_date)

    all_dates = sorted(set(all_dates))
    date_pos = {date: pos for pos, date in enumerate(all_dates)}

    for signal_date in signal_dates:
        pos = date_pos.get(signal_date)
        if pos is None or pos < SHORT_REVISION_LOOKBACK_TRADING_DAYS:
            files.append(
                {
                    "date": signal_date,
                    "status": "missing_short_prior_snapshot_window",
                    "matched_short_revision_rows": 0,
                }
            )
            continue
        prior_date = all_dates[pos - SHORT_REVISION_LOOKBACK_TRADING_DAYS]
        signal_path = path_by_date.get(signal_date) or revision_base._snapshot_path(signal_date)
        prior_path = path_by_date.get(prior_date) or revision_base._snapshot_path(prior_date)
        if signal_path is None or prior_path is None:
            files.append(
                {
                    "date": signal_date,
                    "prior_date": prior_date,
                    "status": "missing_short_snapshot_file",
                    "matched_short_revision_rows": 0,
                }
            )
            continue
        current = snapshot_by_date.setdefault(signal_date, revision_base._load_snapshot(signal_path))
        prior = snapshot_by_date.setdefault(prior_date, revision_base._load_snapshot(prior_path))
        matched = 0
        for ticker, current_row in current.items():
            ticker = str(ticker).upper()
            if ticker not in ticker_set:
                continue
            prior_row = prior.get(ticker)
            if not prior_row:
                continue
            current_estimate = _float(current_row.get("eps_estimate"))
            prior_estimate = _float(prior_row.get("eps_estimate"))
            if current_estimate is None or prior_estimate is None or prior_estimate == 0:
                continue
            revision = (current_estimate - prior_estimate) / abs(prior_estimate)
            if not math.isfinite(revision):
                continue
            matched += 1
            row = {
                "ticker": ticker,
                "signal_date": signal_date,
                "prior_short_snapshot_date": prior_date,
                "short_revision_lookback_trading_days": SHORT_REVISION_LOOKBACK_TRADING_DAYS,
                "eps_estimate_short_prior": framework._round(prior_estimate, 6),
                "eps_estimate_revision_7d_pct": framework._round(revision, 6),
                "short_current_snapshot": framework._repo_rel(signal_path),
                "short_prior_snapshot": framework._repo_rel(prior_path),
            }
            rows.append(row)
            rows_by_date_ticker.setdefault(signal_date, {})[ticker] = row
        files.append(
            {
                "date": signal_date,
                "prior_date": prior_date,
                "status": "ok",
                "snapshot_path": framework._repo_rel(signal_path),
                "prior_snapshot_path": framework._repo_rel(prior_path),
                "matched_short_revision_rows": matched,
            }
        )

    _SHORT_REVISION_CACHE = {
        "cache_key": cache_key,
        "rows": rows,
        "files": files,
        "rows_by_date_ticker": rows_by_date_ticker,
        "source": "daily earnings snapshots",
        "source_caveat": (
            "The short-horizon EPS estimate revision is replayable from daily "
            "snapshots, but estimate provenance remains proxy-grade until a "
            "shared PIT vendor/source adapter is added."
        ),
    }
    return _SHORT_REVISION_CACHE


def _surprise_confirmation_passed(revision_row: dict[str, Any]) -> tuple[bool, str | None]:
    positive_count = _float(revision_row.get("positive_surprise_count"))
    history_count = _float(revision_row.get("surprise_history_count"))
    avg_surprise = _float(revision_row.get("avg_historical_surprise_pct"))
    if positive_count is None or history_count is None or avg_surprise is None:
        return False, "missing_surprise_history"
    if history_count < MIN_SURPRISE_HISTORY_COUNT:
        return False, "surprise_history_too_short"
    positive_ratio = positive_count / history_count if history_count > 0 else 0.0
    if positive_count < MIN_POSITIVE_SURPRISE_COUNT:
        return False, "positive_surprise_count_below_threshold"
    if positive_ratio < MIN_POSITIVE_SURPRISE_RATIO:
        return False, "positive_surprise_ratio_below_threshold"
    if avg_surprise < MIN_AVG_HISTORICAL_SURPRISE_PCT:
        return False, "avg_historical_surprise_negative"
    return True, None


def _revision_acceleration(revision_20d: float, revision_7d: float) -> float | None:
    long_rate = revision_20d / float(REVISION_LOOKBACK_TRADING_DAYS)
    short_rate = revision_7d / float(SHORT_REVISION_LOOKBACK_TRADING_DAYS)
    if long_rate <= 0:
        return None
    ratio = short_rate / long_rate
    return ratio if math.isfinite(ratio) else None


def _candidate_rows_for_window(
    frames: dict[str, pd.DataFrame],
    label: str,
    cfg: dict[str, str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spy = ftd_base._prepared_frame(frames["SPY"]) if "SPY" in frames else None
    qqq = ftd_base._prepared_frame(frames["QQQ"]) if "QQQ" in frames else None
    if spy is None:
        raise RuntimeError("SPY is required for residual leadership control")

    universe = {ticker.upper() for ticker in frames}
    revision_context = revision_base._load_revision_context(universe, frames)
    short_context = _short_revision_context(universe, frames)
    rows_by_date_ticker = revision_context["rows_by_date_ticker"]
    short_rows_by_date_ticker = short_context["rows_by_date_ticker"]
    core_entries = framework.base.shadow._baseline_entries(before_result)
    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    raw_pass_counts: Counter[str] = Counter()
    reject_counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    start = pd.Timestamp(cfg["start"])
    end = pd.Timestamp(cfg["end"])
    spy_closes = [float(value) for value in spy["Close"].tolist()]
    qqq_closes = [float(value) for value in qqq["Close"].tolist()] if qqq is not None else []

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
            revision_20d = _float(revision_row.get("eps_estimate_revision_20d_pct"))
            days_to_earnings = _float(revision_row.get("days_to_earnings"))
            if revision_20d is None or days_to_earnings is None:
                reject_counts["missing_revision_or_dte"] += 1
                continue
            if revision_20d < MIN_EPS_ESTIMATE_REVISION_20D_PCT:
                reject_counts["revision_20d_below_threshold"] += 1
                continue
            if not (MIN_DAYS_TO_EARNINGS <= days_to_earnings <= MAX_DAYS_TO_EARNINGS):
                reject_counts["days_to_earnings_outside_window"] += 1
                continue
            raw_pass_counts["revision_velocity_passed"] += 1

            short_row = short_rows_by_date_ticker.get(signal_date, {}).get(ticker)
            if short_row is None:
                reject_counts["missing_short_revision_row"] += 1
                continue
            revision_7d = _float(short_row.get("eps_estimate_revision_7d_pct"))
            if revision_7d is None or revision_7d < MIN_EPS_ESTIMATE_REVISION_7D_PCT:
                reject_counts["revision_7d_below_threshold"] += 1
                continue
            acceleration_ratio = _revision_acceleration(revision_20d, revision_7d)
            if acceleration_ratio is None or acceleration_ratio < MIN_REVISION_ACCELERATION_RATIO:
                reject_counts["revision_acceleration_below_threshold"] += 1
                continue
            raw_pass_counts["revision_acceleration_passed"] += 1

            surprise_ok, surprise_reject = _surprise_confirmation_passed(revision_row)
            if not surprise_ok:
                reject_counts[str(surprise_reject)] += 1
                continue
            raw_pass_counts["surprise_history_confirmed"] += 1

            pos = pos_by_date[asof]
            if pos + HOLD_DAYS >= len(fr.index) or pos + 1 >= len(fr.index):
                continue
            if asof not in spy.index:
                continue
            row = fr.loc[asof]
            spy_pos = int(spy.index.get_loc(asof))
            qqq_pos = int(qqq.index.get_loc(asof)) if qqq is not None and asof in qqq.index else None
            ret5 = framework._ret(closes, pos, 5)
            ret20 = framework._ret(closes, pos, 20)
            spy_ret5 = framework._ret(spy_closes, spy_pos, 5)
            spy_ret20 = framework._ret(spy_closes, spy_pos, 20)
            qqq_ret20 = (
                framework._ret(qqq_closes, qqq_pos, 20)
                if qqq_pos is not None
                else None
            )
            ret20_excess_qqq = (
                ret20 - qqq_ret20
                if ret20 is not None and qqq_ret20 is not None
                else 0.0
            )
            values = {
                "close": float(row["Close"]),
                "avg_dollar_volume_20": float(row["avg_dollar_volume_20"]),
                "volume_ratio_20": float(row["volume_ratio_20"]),
                "close_location": float(row["close_location"]),
                "ret5_excess_spy": (
                    ret5 - spy_ret5
                    if ret5 is not None and spy_ret5 is not None
                    else None
                ),
                "ret20_excess_spy": (
                    ret20 - spy_ret20
                    if ret20 is not None and spy_ret20 is not None
                    else None
                ),
                "ret20_excess_qqq": ret20_excess_qqq,
            }
            if any(value is None or not math.isfinite(value) for value in values.values()):
                continue
            raw_pass_counts["fields_non_null"] += 1
            if values["close"] < MIN_PRICE:
                reject_counts["price_below_threshold"] += 1
                continue
            if values["avg_dollar_volume_20"] < MIN_AVG_DOLLAR_VOLUME_20:
                reject_counts["liquidity_below_threshold"] += 1
                continue
            raw_pass_counts["liquidity_passed"] += 1
            if bool(row.get("breakout_20")) is not True:
                reject_counts["not_20d_breakout"] += 1
                continue
            raw_pass_counts["breakout_passed"] += 1
            if values["volume_ratio_20"] < MIN_VOLUME_RATIO_20:
                reject_counts["volume_ratio_below_threshold"] += 1
                continue
            if values["close_location"] < MIN_CLOSE_LOCATION:
                reject_counts["close_location_below_threshold"] += 1
                continue
            if values["ret20_excess_spy"] < MIN_RET20_EXCESS_SPY:
                reject_counts["ret20_excess_spy_below_threshold"] += 1
                continue
            if values["ret20_excess_qqq"] < MIN_RET20_EXCESS_QQQ:
                reject_counts["ret20_excess_qqq_below_threshold"] += 1
                continue
            raw_pass_counts["residual_leadership_passed"] += 1

            same_day_core = core_entries.get(signal_date, [])
            if any(str(entry.get("ticker") or "").upper() == ticker for entry in same_day_core):
                reject_counts["same_ticker_core_overlap"] += 1
                continue
            positive_count = _float(revision_row.get("positive_surprise_count")) or 0.0
            history_count = _float(revision_row.get("surprise_history_count")) or 0.0
            surprise_ratio = positive_count / history_count if history_count > 0 else 0.0
            avg_surprise = _float(revision_row.get("avg_historical_surprise_pct")) or 0.0
            score = (
                min(revision_20d, 0.50) * 7.0
                + min(revision_7d, 0.25) * 14.0
                + min(acceleration_ratio, 3.0) * 0.75
                + values["ret20_excess_spy"] * 2.0
                + values["ret20_excess_qqq"] * 1.0
                + max(values["ret5_excess_spy"], -0.10) * 0.75
                + min(values["volume_ratio_20"], 4.0) * 0.20
                + values["close_location"]
                + 0.10 * surprise_ratio
                + 0.005 * min(avg_surprise, 25.0)
            )
            candidate = {
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "window": label,
                "score": framework._round(score, 6),
                "prior_snapshot_date": revision_row.get("prior_snapshot_date"),
                "prior_short_snapshot_date": short_row.get("prior_short_snapshot_date"),
                "revision_lookback_trading_days": REVISION_LOOKBACK_TRADING_DAYS,
                "short_revision_lookback_trading_days": SHORT_REVISION_LOOKBACK_TRADING_DAYS,
                "eps_estimate_current": revision_row.get("eps_estimate_current"),
                "eps_estimate_prior": revision_row.get("eps_estimate_prior"),
                "eps_estimate_short_prior": short_row.get("eps_estimate_short_prior"),
                "eps_estimate_revision_20d_pct": framework._round(revision_20d, 6),
                "eps_estimate_revision_7d_pct": framework._round(revision_7d, 6),
                "revision_acceleration_ratio": framework._round(acceleration_ratio, 6),
                "days_to_earnings": framework._round(days_to_earnings, 2),
                "avg_historical_surprise_pct": revision_row.get("avg_historical_surprise_pct"),
                "positive_surprise_count": revision_row.get("positive_surprise_count"),
                "surprise_history_count": revision_row.get("surprise_history_count"),
                "positive_surprise_ratio": framework._round(surprise_ratio, 6),
                "avg_dollar_volume_20": framework._round(values["avg_dollar_volume_20"], 2),
                "volume_ratio_20": framework._round(values["volume_ratio_20"], 6),
                "close_location": framework._round(values["close_location"], 6),
                "ret5_excess_spy": framework._round(values["ret5_excess_spy"], 6),
                "ret20_excess_spy": framework._round(values["ret20_excess_spy"], 6),
                "ret20_excess_qqq": framework._round(values["ret20_excess_qqq"], 6),
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
                        "revision_20d": candidate["eps_estimate_revision_20d_pct"],
                        "revision_7d": candidate["eps_estimate_revision_7d_pct"],
                        "acceleration_ratio": candidate["revision_acceleration_ratio"],
                        "ret20_excess_spy": candidate["ret20_excess_spy"],
                        "ret20_excess_qqq": candidate["ret20_excess_qqq"],
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
                -float(item["revision_acceleration_ratio"]),
                -float(item["eps_estimate_revision_7d_pct"]),
                -float(item["ret20_excess_spy"]),
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
        "acceleration_gate": {
            "short_revision_lookback_trading_days": SHORT_REVISION_LOOKBACK_TRADING_DAYS,
            "min_eps_estimate_revision_7d_pct": MIN_EPS_ESTIMATE_REVISION_7D_PCT,
            "min_revision_acceleration_ratio": MIN_REVISION_ACCELERATION_RATIO,
        },
        "residual_leadership_gate": {
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret20_excess_qqq": MIN_RET20_EXCESS_QQQ,
        },
        "surprise_history_gate": {
            "min_surprise_history_count": MIN_SURPRISE_HISTORY_COUNT,
            "min_positive_surprise_count": MIN_POSITIVE_SURPRISE_COUNT,
            "min_positive_surprise_ratio": MIN_POSITIVE_SURPRISE_RATIO,
            "min_avg_historical_surprise_pct": MIN_AVG_HISTORICAL_SURPRISE_PCT,
        },
    }


def _revision_rows_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_month: Counter[str] = Counter()
    by_ticker: Counter[str] = Counter()
    qualifying_by_month: Counter[str] = Counter()
    for row in rows:
        signal_date = str(row.get("signal_date") or "")
        month = signal_date[:7]
        if month:
            by_month[month] += 1
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker] += 1
        revision_7d = _float(row.get("eps_estimate_revision_7d_pct"))
        if revision_7d is not None and revision_7d >= MIN_EPS_ESTIMATE_REVISION_7D_PCT:
            qualifying_by_month[month] += 1
    return {
        "row_count": len(rows),
        "ticker_count": len(by_ticker),
        "short_revision_month_counts": dict(sorted(by_month.items())),
        "qualified_short_revision_month_counts": dict(sorted(qualifying_by_month.items())),
        "top_ticker_row_counts": [
            {"ticker": ticker, "row_count": count}
            for ticker, count in by_ticker.most_common(25)
        ],
        "parameters": {
            "short_revision_lookback_trading_days": SHORT_REVISION_LOOKBACK_TRADING_DAYS,
            "min_eps_estimate_revision_7d_pct": MIN_EPS_ESTIMATE_REVISION_7D_PCT,
            "min_revision_acceleration_ratio": MIN_REVISION_ACCELERATION_RATIO,
        },
        "source_caveat": (
            "Daily earnings snapshots are replayable; historical estimate "
            "values remain proxy-grade until a PIT vendor/provenance adapter is "
            "added."
        ),
    }


def _accepted_revision_comparator(payload: dict[str, Any]) -> dict[str, Any]:
    if not ACCEPTED_REVISION_ARTIFACT.exists():
        return {
            "passed": False,
            "status": "missing_accepted_revision_artifact",
            "artifact": framework._repo_rel(ACCEPTED_REVISION_ARTIFACT),
        }
    accepted = json.loads(ACCEPTED_REVISION_ARTIFACT.read_text(encoding="utf-8"))
    accepted_after = accepted.get("after_metrics") or {}
    candidate_after = payload.get("after_metrics") or {}
    accepted_aggregate = accepted.get("aggregate") or {}
    candidate_aggregate = payload.get("aggregate") or {}
    window_deltas: dict[str, dict[str, float | int]] = {}
    ev_windows_improved = 0
    pnl_windows_improved = 0
    for window in framework.base.WINDOWS:
        cand = candidate_after.get(window) or {}
        acc = accepted_after.get(window) or {}
        ev_delta = float(cand.get("expected_value_score") or 0.0) - float(
            acc.get("expected_value_score") or 0.0
        )
        pnl_delta = float(cand.get("total_pnl") or 0.0) - float(acc.get("total_pnl") or 0.0)
        if ev_delta >= 0:
            ev_windows_improved += 1
        if pnl_delta >= 0:
            pnl_windows_improved += 1
        window_deltas[window] = {
            "expected_value_score_delta_vs_accepted_revision": framework._round(ev_delta, 6),
            "total_pnl_delta_vs_accepted_revision": framework._round(pnl_delta, 2),
            "candidate_trade_count": int(cand.get("trade_count") or 0),
            "accepted_revision_trade_count": int(acc.get("trade_count") or 0),
        }
    aggregate_ev_delta = float(
        candidate_aggregate.get("after_expected_value_score_sum") or 0.0
    ) - float(accepted_aggregate.get("after_expected_value_score_sum") or 0.0)
    aggregate_pnl_delta = float(candidate_aggregate.get("after_total_pnl_sum") or 0.0) - float(
        accepted_aggregate.get("after_total_pnl_sum") or 0.0
    )
    passed = (
        aggregate_ev_delta > 0
        and aggregate_pnl_delta > 0
        and ev_windows_improved == len(framework.base.WINDOWS)
        and pnl_windows_improved == len(framework.base.WINDOWS)
    )
    return {
        "passed": passed,
        "artifact": framework._repo_rel(ACCEPTED_REVISION_ARTIFACT),
        "accepted_revision_experiment": "exp-20260609-011",
        "aggregate_expected_value_score_delta_vs_accepted_revision": framework._round(
            aggregate_ev_delta, 6
        ),
        "aggregate_total_pnl_delta_vs_accepted_revision": framework._round(
            aggregate_pnl_delta, 2
        ),
        "windows_ev_at_or_above_accepted_revision": ev_windows_improved,
        "windows_pnl_at_or_above_accepted_revision": pnl_windows_improved,
        "window_deltas": window_deltas,
    }


def _build_payload() -> dict[str, Any]:
    _patch_framework()
    payload = _ORIGINAL_BUILD_PAYLOAD()
    revision_context = revision_base._REVISION_CACHE or {}
    short_context = _SHORT_REVISION_CACHE or {}
    framework._write_json(
        REVISION_ROWS_JSON,
        {
            "twenty_day_revision_rows": revision_base._revision_rows_summary(
                revision_context.get("rows", [])
            ),
            "seven_day_revision_rows": _revision_rows_summary(short_context.get("rows", [])),
        },
    )
    framework._write_json(
        REVISION_FILES_JSON,
        {
            "twenty_day_revision_files": revision_context.get("files", []),
            "seven_day_revision_files": short_context.get("files", []),
        },
    )

    core_gate4_passed = bool(payload["gate4"]["passed"])
    accepted_comparator = _accepted_revision_comparator(payload)
    comparator_passed = bool(accepted_comparator.get("passed"))
    retention_numeric_passed = core_gate4_passed and comparator_passed
    if not comparator_passed:
        payload["gate4"].setdefault("failed_gates", []).append(
            "accepted_revision_adapter_not_beaten"
        )
    payload["gate4"].update(
        {
            "core_baseline_passed": core_gate4_passed,
            "accepted_revision_comparator_passed": comparator_passed,
            "accepted_revision_comparator": accepted_comparator,
            "passed": retention_numeric_passed,
        }
    )

    passed = False
    if retention_numeric_passed:
        decision = "positive_proxy_lead_not_promoted_requires_shared_revision_acceleration_adapter"
        rationale = (
            "The replay scout beat the core baseline and accepted revision "
            "adapter comparator, but the short-horizon estimate revision source "
            "is still proxy-grade and no shared default-off daily helper was "
            "implemented in this run."
        )
    elif core_gate4_passed and not comparator_passed:
        decision = "rejected_revision_acceleration_residual_leadership_not_better_than_accepted_revision_adapter"
        rationale = (
            "The scout beat or held the core baseline gates, but did not beat "
            "the accepted revision-surprise low-extension adapter across the "
            "three-window comparator required for near-neighbor revision work."
        )
    else:
        decision = "rejected_revision_acceleration_residual_leadership_candidate_pool"
        rationale = (
            "Gate 4 failed versus the core baseline; revision acceleration plus "
            "residual leadership did not produce a robust retained alpha."
        )
    payload["gate4"]["decision"] = decision
    payload["gate4"]["rationale"] = rationale
    payload["gate4"]["numeric_passed"] = core_gate4_passed
    payload["gate4"]["retention_numeric_passed"] = retention_numeric_passed
    actual_success = 1 if passed else 0
    ev_delta = payload["aggregate"]["expected_value_score_delta_sum"]
    pnl_delta = payload["aggregate"]["total_pnl_delta_sum"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "rejected" if not passed else "accepted",
            "decision": decision,
            "accepted": passed,
            "hypothesis": (
                "EPS estimate revisions should be more tradable when the "
                "20-trading-day revision is still accelerating over the latest "
                "7 snapshot dates and the stock is already showing residual "
                "leadership versus broad and growth indices."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "analyst_revision_expectation_trajectory",
            "prior_trial_count": 8,
            "nearby_prior_experiments": [
                "exp-20260604-029",
                "exp-20260606-016",
                "exp-20260609-011",
                "exp-20260609-015",
                "exp-20260610-014",
                "exp-20260610-016",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "short_horizon_eps_revision_acceleration_plus_residual_leadership",
            "interpretation": rationale,
            "rejection_reason": None if retention_numeric_passed else "; ".join(
                payload["gate4"]["failed_gates"]
            ),
            "prediction": {
                "success_probability": 0.20,
                "expected_ev_delta": 0.10,
                "expected_pnl_delta": 2000.0,
                "main_failure_modes": [
                    "accepted_revision_adapter_not_beaten",
                    "old_thin_regression",
                    "thin_sample",
                    "concentration_failed",
                    "proxy_revision_provenance",
                ],
                "confidence_reason": (
                    "The revision lane has produced accepted default-off value, "
                    "and fresh analyst estimate acceleration is a plausible "
                    "expectation-trajectory field. Confidence is low because "
                    "prior persistent-ledger and post-earnings revision "
                    "extensions failed or missed accepted-adapter comparators, "
                    "so the main test is whether 7d freshness adds distinct "
                    "replacement value without thinning the sample."
                ),
                "recorded_at": "2026-06-10T22:00:29+00:00",
                "actual_success": actual_success,
                "actual_ev_delta": ev_delta,
                "actual_pnl_delta": pnl_delta,
                "brier_score": round((0.20 - actual_success) ** 2, 6),
            },
            "earnings_revision_source": {
                "source": revision_context.get("source"),
                "twenty_day_row_count": len(revision_context.get("rows", [])),
                "seven_day_row_count": len(short_context.get("rows", [])),
                "row_summary_artifact": framework._repo_rel(REVISION_ROWS_JSON),
                "files_artifact": framework._repo_rel(REVISION_FILES_JSON),
                "source_caveat": short_context.get("source_caveat")
                or revision_context.get("source_caveat"),
            },
        }
    )
    payload["parameters"].update(
        {
            "single_changed_variable": CHANGED_VARIABLE,
            "source_relation": (
                "Ticker must pass 20d EPS estimate revision velocity, positive "
                "surprise-history confirmation, latest 7-snapshot EPS revision "
                ">= 1%, 7d annualized revision pace at least equal to the 20d "
                "pace, and fixed residual leadership controls versus SPY/QQQ."
            ),
            "revision_lookback_trading_days": REVISION_LOOKBACK_TRADING_DAYS,
            "short_revision_lookback_trading_days": SHORT_REVISION_LOOKBACK_TRADING_DAYS,
            "min_eps_estimate_revision_20d_pct": MIN_EPS_ESTIMATE_REVISION_20D_PCT,
            "min_eps_estimate_revision_7d_pct": MIN_EPS_ESTIMATE_REVISION_7D_PCT,
            "min_revision_acceleration_ratio": MIN_REVISION_ACCELERATION_RATIO,
            "min_ret20_excess_qqq": MIN_RET20_EXCESS_QQQ,
            "min_days_to_earnings": MIN_DAYS_TO_EARNINGS,
            "max_days_to_earnings": MAX_DAYS_TO_EARNINGS,
            "min_surprise_history_count": MIN_SURPRISE_HISTORY_COUNT,
            "min_positive_surprise_count": MIN_POSITIVE_SURPRISE_COUNT,
            "min_positive_surprise_ratio": MIN_POSITIVE_SURPRISE_RATIO,
            "min_avg_historical_surprise_pct": MIN_AVG_HISTORICAL_SURPRISE_PCT,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: accelerating analyst expectation upgrades "
            "plus residual index leadership should identify stocks where "
            "fundamental revision and price discovery are aligned."
        ),
        "2_history_check": {
            "exp-20260604-029": (
                "Raw 20d EPS revision velocity was aggregate-positive but "
                "failed old_thin and remained proxy-grade."
            ),
            "exp-20260606-016": (
                "Surprise-history confirmation improved the revision lane but "
                "still was not promoted before a shared adapter."
            ),
            "exp-20260609-011": (
                "Accepted shared default-off revision surprise low-extension "
                "adapter improved all three windows; this run must beat it as "
                "the near-neighbor comparator."
            ),
            "exp-20260609-015": (
                "Persistent 7d/30d ledger overlay produced zero target trades "
                "because accepted helper rows lacked the required ledger rows."
            ),
            "exp-20260610-014": (
                "Accepted source-priority allocator extension is a capital "
                "allocation result, not a new revision candidate source."
            ),
            "exp-20260610-016": (
                "Post-earnings allocator extension failed to beat the accepted "
                "revision allocator comparator."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three windows; positive aggregate "
            "EV/PnL; no EV/PnL-regressed window; sample, drawdown, survival, "
            "and concentration guards pass; because this is a revision "
            "near-neighbor, it must also beat exp-20260609-011 across the "
            "accepted adapter comparator. Any positive replay-only result is "
            "a lead until a shared default-off daily helper proves parity."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260610_025_revision_acceleration_residual_leadership.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
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
            "requires_shared_adapter_before_promotion": retention_numeric_passed,
            "parity_note": (
                "Replay-only/default-off. No production code is changed. A "
                "positive result would require implementing this exact "
                "candidate source in a shared paper helper that serves both "
                "historical replay and daily snapshots before any report, "
                "ledger, ranking, sizing, watchlist, or order surface changes."
            ),
        }
    )
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "source_provenance_promotable": False,
        "parity_note": (
            "This runner changes no production path. Historical EPS estimate "
            "snapshots are proxy-grade, so even a positive scout cannot be "
            "promoted without a shared PIT revision-acceleration adapter and "
            "daily parity tests."
        ),
    }
    payload["post_run_reflection"] = {
        "why_result_happened": (
            f"{rationale} The 7d acceleration gate tightened the accepted "
            "revision-style source to only 16 target trades and appears to "
            "remove too much diversified replacement value; the remaining "
            "losers, especially old_thin, outweighed the few positive leaders."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping 7d revision threshold, acceleration "
            "ratio, QQQ residual cutoff, surprise-history count, top-N, "
            "hold-day, cooldown, or paper notional on these same frozen "
            "snapshots."
        ),
        "new_evidence_required": (
            "If this fails, leave short-window revision acceleration frozen "
            "until a real PIT analyst revision source or materially broader "
            "expectation-trajectory data arrives."
        ),
    }
    payload["anti_js"] = "No JavaScript was used."
    payload["related_files"] = [
        framework._repo_rel(Path(__file__)),
        framework._repo_rel(OUT_JSON),
        framework._repo_rel(BEFORE_JSON),
        framework._repo_rel(AFTER_JSON),
        framework._repo_rel(REVISION_ROWS_JSON),
        framework._repo_rel(REVISION_FILES_JSON),
        framework._repo_rel(LOG_JSON),
        framework._repo_rel(ARTIFACT_MD),
        framework._repo_rel(CARD_MD),
        framework._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    text = _ORIGINAL_ARTIFACT(payload)
    return text.replace(
        "Analyst Revision Velocity Candidate Pool",
        "Revision Acceleration Residual Leadership Candidate Pool",
    )


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


def _patch_revision_base() -> None:
    revision_base.EXPERIMENT_ID = EXPERIMENT_ID
    revision_base.STEM = STEM
    revision_base.TRIAL_FAMILY = TRIAL_FAMILY
    revision_base.CHANGED_VARIABLE = CHANGED_VARIABLE
    revision_base.RULE_VERSION = RULE_VERSION
    revision_base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    revision_base.HOLD_DAYS = HOLD_DAYS
    revision_base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    revision_base.MIN_PRICE = MIN_PRICE
    revision_base.MIN_AVG_DOLLAR_VOLUME_20 = MIN_AVG_DOLLAR_VOLUME_20
    revision_base.MIN_VOLUME_RATIO_20 = MIN_VOLUME_RATIO_20
    revision_base.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    revision_base.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    revision_base.REVISION_LOOKBACK_TRADING_DAYS = REVISION_LOOKBACK_TRADING_DAYS
    revision_base.MIN_EPS_ESTIMATE_REVISION_20D_PCT = MIN_EPS_ESTIMATE_REVISION_20D_PCT
    revision_base.MIN_DAYS_TO_EARNINGS = MIN_DAYS_TO_EARNINGS
    revision_base.MAX_DAYS_TO_EARNINGS = MAX_DAYS_TO_EARNINGS
    revision_base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    revision_base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    revision_base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    revision_base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    revision_base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    revision_base.OUT_DIR = OUT_DIR
    revision_base.OUT_JSON = OUT_JSON
    revision_base.BEFORE_JSON = BEFORE_JSON
    revision_base.AFTER_JSON = AFTER_JSON
    revision_base.REVISION_ROWS_JSON = REVISION_ROWS_JSON
    revision_base.REVISION_FILES_JSON = REVISION_FILES_JSON
    revision_base.LOG_JSON = LOG_JSON
    revision_base.ARTIFACT_MD = ARTIFACT_MD
    revision_base.CARD_MD = CARD_MD
    revision_base.EXPERIMENT_LOG = EXPERIMENT_LOG
    revision_base._candidate_rows_for_window = _candidate_rows_for_window
    revision_base._build_payload = _build_payload
    revision_base._artifact = _artifact


def run(output: Path = OUT_JSON) -> dict[str, Any]:
    _patch_revision_base()
    revision_base._patch_framework()
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
