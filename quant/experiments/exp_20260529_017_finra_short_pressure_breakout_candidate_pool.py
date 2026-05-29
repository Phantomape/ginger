"""exp-20260529-017: FINRA short-pressure breakout candidate pool.

This alpha search tests one free, production-visible data source: FINRA
biweekly short interest with publication-date lag. The candidate source is
default-off paper only. It selects liquid stock breakouts whose latest
published short-interest context ranks highly versus the same-day universe.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import csv
import io
import json
import math
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

import exp_20260528_037_ticker_accumulation_quality_breakout as framework


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_short_interest_shadow_experiment as short_base  # noqa: E402


EXPERIMENT_ID = "exp-20260529-017"
STEM = "finra_short_pressure_breakout_candidate_pool"
TRIAL_FAMILY = "finra_short_pressure_breakout_candidate_pool"
CHANGED_VARIABLE = "finra_short_pressure_breakout_candidate_source_v1"
RULE_VERSION = "finra_short_pressure_breakout_candidate_source_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260529_017_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
FINRA_ROWS_JSON = OUT_DIR / "finra_short_interest_rows.json"
FINRA_FILES_JSON = OUT_DIR / "finra_source_files.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BREAKOUT_LOOKBACK_DAYS = 20
MOVING_AVERAGE_DAYS = 50
RELATIVE_STRENGTH_DAYS = 20
VOLUME_RATIO_DAYS = 20
MIN_CLOSE = 5.0
MIN_DOLLAR_VOLUME = 30_000_000.0
MIN_VOLUME_RATIO_20D = 1.10
MIN_SIGNAL_CLOSE_LOCATION = 0.60
MIN_RS20_VS_SPY = 0.0
MIN_SHORT_PRESSURE_SCORE = 0.70
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

_FINRA_CACHE: dict[str, Any] | None = None


def _current_finra_context() -> dict[str, Any]:
    if _FINRA_CACHE is None:
        raise RuntimeError("FINRA context was not loaded before payload postprocess")
    return _FINRA_CACHE


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
    framework._gate4 = _gate4
    framework._build_report = _build_report


def _fetch_finra_rows_cached(
    tickers: set[str],
    settlements: list[date],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cache_dir = OUT_DIR / "finra_source_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "ginger-finra-short-pressure-exp-20260529-017/1.0 "
                "research-only local workspace"
            )
        }
    )

    rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for settlement in settlements:
        yyyymmdd = settlement.strftime("%Y%m%d")
        url = short_base.FINRA_CSV_URL.format(yyyymmdd=yyyymmdd)
        cache_path = cache_dir / f"shrt{yyyymmdd}.csv"
        status_code: int | str | None = None
        source = "cache"
        try:
            if cache_path.exists():
                text = cache_path.read_text(encoding="utf-8-sig")
                status_code = "cached"
            else:
                source = "network"
                response = session.get(url, timeout=30)
                status_code = response.status_code
                if response.status_code != 200:
                    files.append(
                        {
                            "settlement_date": settlement.isoformat(),
                            "url": url,
                            "status_code": response.status_code,
                            "matched_rows": 0,
                            "source": source,
                        }
                    )
                    continue
                text = response.content.decode("utf-8-sig")
                cache_path.write_text(text, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - network can vary.
            files.append(
                {
                    "settlement_date": settlement.isoformat(),
                    "url": url,
                    "status_code": status_code,
                    "error": str(exc),
                    "matched_rows": 0,
                    "source": source,
                }
            )
            continue

        publication, pub_method = short_base.publication_date_for(settlement)
        matched = 0
        reader = csv.DictReader(io.StringIO(text), delimiter="|")
        for raw in reader:
            ticker = str(raw.get("symbolCode") or "").upper().strip()
            if ticker not in tickers:
                continue
            matched += 1
            rows.append(
                {
                    "ticker": ticker,
                    "settlement_date": settlement.isoformat(),
                    "publication_date": publication.isoformat(),
                    "usable_trade_date": publication.isoformat(),
                    "publication_date_method": pub_method,
                    "pit_safe": True,
                    "short_interest": short_base.to_int(
                        raw.get("currentShortPositionQuantity")
                    ),
                    "previous_short_interest": short_base.to_int(
                        raw.get("previousShortPositionQuantity")
                    ),
                    "short_interest_change": short_base.to_int(
                        raw.get("changePreviousNumber")
                    ),
                    "short_interest_change_pct": short_base.to_float(
                        raw.get("changePercent")
                    ),
                    "days_to_cover": short_base.to_float(
                        raw.get("daysToCoverQuantity")
                    ),
                    "average_daily_volume": short_base.to_int(
                        raw.get("averageDailyVolumeQuantity")
                    ),
                    "issuer_exchange_code": raw.get("issuerServicesGroupExchangeCode"),
                    "market_class_code": raw.get("marketClassCode"),
                    "issue_name": raw.get("issueName"),
                    "source_url": url,
                }
            )
        files.append(
            {
                "settlement_date": settlement.isoformat(),
                "publication_date": publication.isoformat(),
                "url": url,
                "status_code": status_code,
                "matched_rows": matched,
                "source": source,
                "cache_path": framework.base._repo_rel(cache_path),
            }
        )
    return rows, files


def _load_finra_context(universe: list[str]) -> dict[str, Any]:
    global _FINRA_CACHE
    tickers = set(universe).difference(framework.EXCLUDED_TICKERS)
    if _FINRA_CACHE is not None and _FINRA_CACHE.get("tickers") == sorted(tickers):
        return _FINRA_CACHE

    starts = [datetime.strptime(cfg["start"], "%Y-%m-%d").date() for cfg in framework.base.WINDOWS.values()]
    ends = [datetime.strptime(cfg["end"], "%Y-%m-%d").date() for cfg in framework.base.WINDOWS.values()]
    settlements = short_base.settlement_dates(min(starts) - timedelta(days=45), max(ends))
    rows, files = _fetch_finra_rows_cached(tickers, settlements)
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_ticker.setdefault(row["ticker"], []).append(row)
    for ticker_rows in by_ticker.values():
        ticker_rows.sort(key=lambda row: (row["publication_date"], row["settlement_date"]))

    _FINRA_CACHE = {
        "tickers": sorted(tickers),
        "rows": rows,
        "files": files,
        "rows_by_ticker": by_ticker,
        "settlement_count": len(settlements),
    }
    return _FINRA_CACHE


def _latest_finra_row(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker.upper()) or []
    eligible = [row for row in rows if str(row["publication_date"]) <= signal_date]
    if not eligible:
        return None
    return eligible[-1]


def _percentiles(values: list[float | None]) -> list[float | None]:
    present = sorted(value for value in values if value is not None and math.isfinite(value))
    if not present:
        return [None for _ in values]
    if len(present) == 1:
        return [0.5 if value is not None else None for value in values]
    out: list[float | None] = []
    denom = len(present) - 1
    for value in values:
        if value is None or not math.isfinite(value):
            out.append(None)
            continue
        below_or_equal = sum(1 for other in present if other <= value)
        out.append(round((below_or_equal - 1) / denom, 6))
    return out


def _same_day_short_scores(
    tickers: list[str],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    signal_date: str,
) -> dict[str, dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for ticker in tickers:
        row = _latest_finra_row(rows_by_ticker, ticker, signal_date)
        if row is None:
            continue
        records.append(
            {
                "ticker": ticker,
                "row": row,
                "days_to_cover": row.get("days_to_cover"),
                "short_interest_change_pct": row.get("short_interest_change_pct"),
            }
        )

    crowding_scores = _percentiles(
        [
            float(record["days_to_cover"])
            if isinstance(record.get("days_to_cover"), (int, float))
            else None
            for record in records
        ]
    )
    change_scores = _percentiles(
        [
            float(record["short_interest_change_pct"])
            if isinstance(record.get("short_interest_change_pct"), (int, float))
            else None
            for record in records
        ]
    )

    out: dict[str, dict[str, Any]] = {}
    for record, crowding, change in zip(records, crowding_scores, change_scores):
        crowding_for_score = 0.0 if crowding is None else crowding
        change_for_score = 0.0 if change is None else change
        score = round(0.70 * crowding_for_score + 0.30 * change_for_score, 6)
        out[record["ticker"]] = {
            "finra_row": record["row"],
            "short_crowding_score": crowding,
            "short_change_score": change,
            "finra_short_pressure_score": score,
            "same_day_finra_covered_count": len(records),
            "score_weights": {"days_to_cover_percentile": 0.70, "change_percentile": 0.30},
        }
    return out


def _avg_volume(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values = [
        framework.ohlcv_helper._value(row, "Volume")
        for row in rows[idx - days:idx]
    ]
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return sum(clean) / len(clean)


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    finra_context = _load_finra_context(universe)
    rows_by_ticker = finra_context["rows_by_ticker"]
    entries_by_date = framework.ohlcv_helper._baseline_entries(before_result)
    dates = [
        trading_date
        for trading_date in framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= trading_date <= str(cfg["end"])
    ]
    stock_tickers = sorted(set(universe).intersection(snapshot).difference(framework.EXCLUDED_TICKERS))
    spy_rows = framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = framework.ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    score_cache: dict[str, dict[str, dict[str, Any]]] = {}
    min_idx = max(BREAKOUT_LOOKBACK_DAYS, MOVING_AVERAGE_DAYS, RELATIVE_STRENGTH_DAYS)

    for ticker in stock_tickers:
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx_by_date = framework.ohlcv_helper._row_index(rows)
        for signal_date in dates:
            idx = idx_by_date.get(signal_date)
            spy_idx = spy_index.get(signal_date)
            if idx is None or spy_idx is None or idx < min_idx or spy_idx < RELATIVE_STRENGTH_DAYS:
                audit["insufficient_history"] += 1
                continue

            close = framework.ohlcv_helper._value(rows[idx], "Close")
            high = framework.ohlcv_helper._value(rows[idx], "High")
            volume = framework.ohlcv_helper._value(rows[idx], "Volume")
            if close is None or high is None or volume is None or float(close) < MIN_CLOSE:
                audit["missing_or_low_price_volume"] += 1
                continue
            dollar_volume = float(close) * float(volume)
            if dollar_volume < MIN_DOLLAR_VOLUME:
                audit["low_dollar_volume"] += 1
                continue

            price_prior_high = framework._prior_high(rows, idx, BREAKOUT_LOOKBACK_DAYS, "High")
            ma50 = framework._prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
            if price_prior_high is None or ma50 is None:
                audit["missing_price_context"] += 1
                continue
            if float(close) <= float(price_prior_high) or float(close) <= float(ma50):
                audit["not_price_breakout_or_above_ma50"] += 1
                continue

            avg_volume = _avg_volume(rows, idx, VOLUME_RATIO_DAYS)
            if avg_volume is None or avg_volume <= 0:
                audit["missing_volume_context"] += 1
                continue
            volume_ratio_20d = float(volume) / avg_volume
            if volume_ratio_20d < MIN_VOLUME_RATIO_20D:
                audit["volume_ratio_too_low"] += 1
                continue

            signal_close_location = framework._close_location(rows[idx])
            if (
                signal_close_location is None
                or signal_close_location < MIN_SIGNAL_CLOSE_LOCATION
            ):
                audit["weak_signal_close_location"] += 1
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

            if signal_date not in score_cache:
                score_cache[signal_date] = _same_day_short_scores(
                    stock_tickers,
                    rows_by_ticker,
                    signal_date,
                )
            short_score = score_cache[signal_date].get(ticker)
            if short_score is None:
                audit["missing_published_finra_row"] += 1
                continue
            if short_score["finra_short_pressure_score"] < MIN_SHORT_PRESSURE_SCORE:
                audit["short_pressure_score_too_low"] += 1
                continue

            finra_row = short_score["finra_row"]
            ab_entries = entries_by_date.get(signal_date, [])
            distance_above_price_high = (float(close) / float(price_prior_high)) - 1.0
            selection_score = (
                float(short_score["finra_short_pressure_score"])
                + min(rs20_vs_spy, 0.50)
                + min(volume_ratio_20d / 10.0, 0.25)
                + min(signal_close_location / 10.0, 0.10)
            )
            candidates.append(
                {
                    "ticker": ticker,
                    "date": signal_date,
                    "strategy": STEM,
                    "rule_version": RULE_VERSION,
                    "close": framework.base._round(close, 4),
                    "volume": framework.base._round(volume, 2),
                    "dollar_volume": framework.base._round(dollar_volume, 2),
                    "ma50": framework.base._round(ma50, 4),
                    "price_prior_high_20d": framework.base._round(price_prior_high, 4),
                    "distance_above_price_high_20d": framework.base._round(
                        distance_above_price_high, 6
                    ),
                    "volume_ratio_20d": framework.base._round(volume_ratio_20d, 6),
                    "signal_close_location": framework.base._round(
                        signal_close_location, 6
                    ),
                    "ret20": framework.base._round(ret20, 6),
                    "spy_ret20": framework.base._round(spy_ret20, 6),
                    "rs20_vs_spy": framework.base._round(rs20_vs_spy, 6),
                    "finra_settlement_date": finra_row.get("settlement_date"),
                    "finra_publication_date": finra_row.get("publication_date"),
                    "finra_publication_date_method": finra_row.get(
                        "publication_date_method"
                    ),
                    "finra_days_to_cover": finra_row.get("days_to_cover"),
                    "finra_short_interest": finra_row.get("short_interest"),
                    "finra_previous_short_interest": finra_row.get(
                        "previous_short_interest"
                    ),
                    "finra_short_interest_change": finra_row.get(
                        "short_interest_change"
                    ),
                    "finra_short_interest_change_pct": finra_row.get(
                        "short_interest_change_pct"
                    ),
                    "finra_average_daily_volume": finra_row.get(
                        "average_daily_volume"
                    ),
                    "finra_short_crowding_score": short_score.get(
                        "short_crowding_score"
                    ),
                    "finra_short_change_score": short_score.get(
                        "short_change_score"
                    ),
                    "finra_short_pressure_score": short_score[
                        "finra_short_pressure_score"
                    ],
                    "same_day_finra_covered_count": short_score[
                        "same_day_finra_covered_count"
                    ],
                    "finra_source_url": finra_row.get("source_url"),
                    "candidate_selection_score": framework.base._round(
                        selection_score, 6
                    ),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "known_at": "after_signal_date_close_with_latest_published_finra_before_next_open_paper_entry",
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_selection_score"]),
            -float(row["finra_short_pressure_score"]),
            -float(row["rs20_vs_spy"]),
            -float(row["volume_ratio_20d"]),
            -float(row["dollar_volume"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "candidate_universe_argument_count": len(universe),
        "stock_tickers_checked": len(stock_tickers),
        "finra_rows_loaded": len(finra_context["rows"]),
        "finra_files_attempted": len(finra_context["files"]),
        "finra_files_ok_or_cached": sum(
            1
            for item in finra_context["files"]
            if item.get("status_code") in (200, "cached")
        ),
        "rule_version": RULE_VERSION,
        "audit_reject_counts": dict(sorted(audit.items())),
    }


def _gate4(
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    min_survival: float,
) -> dict[str, Any]:
    target_windows = target_summary["windows_with_target_trades"]
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
    )
    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive")
    if aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("survival_guardrail_failed")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    return {
        "passed": passed,
        "failed_reasons": failed,
        "aggregate_ev_delta_positive": aggregate["expected_value_score_delta_sum"] > 0,
        "aggregate_pnl_delta_positive": aggregate["total_pnl_delta_sum"] > 0,
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    finra_context = _current_finra_context()
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_finra_short_pressure_breakout"
        if gate4["passed"]
        else "rejected_finra_short_pressure_breakout"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.24,
        "expected_ev_delta": 0.18,
        "expected_pnl_delta": 3500.0,
        "main_failure_modes": [
            "sample_too_thin",
            "late_strong_regression",
            "short_pressure_false_positive",
            "concentration",
        ],
        "confidence_reason": (
            "FINRA short interest is an orthogonal free PIT source, but the "
            "publication lag and recent candidate-pool failures lower confidence."
        ),
        "recorded_at": "2026-05-29T15:06:14+00:00",
        "brier_score": round((0.24 - actual_success) ** 2, 6),
    }

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "FINRA publication-lag short-interest pressure plus OHLCV breakout "
                "confirmation may create a free-data default-off candidate pool."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 2,
            "nearby_prior_experiments": [
                "exp-20260505-024",
                "exp-20260506-free-short-pressure",
                "exp-20260528-037",
                "exp-20260529-001",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "production_visible_free_finra_short_interest_pit_field",
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(framework.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "breakout_lookback_days": BREAKOUT_LOOKBACK_DAYS,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "relative_strength_days": RELATIVE_STRENGTH_DAYS,
                "volume_ratio_days": VOLUME_RATIO_DAYS,
                "min_close": MIN_CLOSE,
                "min_dollar_volume": MIN_DOLLAR_VOLUME,
                "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
                "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
                "min_rs20_vs_spy": MIN_RS20_VS_SPY,
                "min_short_pressure_score": MIN_SHORT_PRESSURE_SCORE,
                "finra_score_definition": {
                    "days_to_cover_percentile_weight": 0.70,
                    "short_interest_change_pct_percentile_weight": 0.30,
                    "same_day_universe": (
                        "current fixed-window stock universe with a published "
                        "FINRA row on or before the signal date"
                    ),
                },
                "source_definition": [
                    "latest FINRA short-interest row must be published on or before the signal date",
                    "short-pressure score must be at least 0.70",
                    "stock ticker only; ETFs and benchmark/theme proxies excluded",
                    "close above prior 20-day high",
                    "close above prior 50-day moving average",
                    "signal-day volume / prior-20-day average volume >= 1.10",
                    "signal-day close location >= 0.60",
                    "20-day return exceeds SPY",
                    "signal-day dollar volume >= USD 30 million",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "candidate_selection_score desc",
                    "finra_short_pressure_score desc",
                    "rs20_vs_spy desc",
                    "volume_ratio_20d desc",
                    "dollar_volume desc",
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
                    "candidate_pool / entry: high published short-interest pressure "
                    "can amplify liquid breakouts through squeeze/covering demand, "
                    "but only when price/volume/RS already confirm."
                ),
                "2_history_check": {
                    "exp-20260505-024": (
                        "FINRA days-to-cover was joined as a shadow overlay only; "
                        "it did not run a three-window paper candidate-pool replay."
                    ),
                    "exp-20260506-free-short-pressure": (
                        "Added SEC FTD/Nasdaq threshold as shadow context only; "
                        "no default-off paper candidate source was tested."
                    ),
                    "exp-20260528-037_and_exp-20260529-001": (
                        "OHLCV-only accumulation/VWAP candidate pools failed; this "
                        "run adds an orthogonal official short-interest field instead "
                        "of retuning a price pattern."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                    "no EV- or PnL-regressed window; >=20 paper trades across all 3 "
                    "windows; drawdown drift <=0.5pp; survival >=5%; concentration "
                    "inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260529_017_finra_short_pressure_breakout_candidate_pool.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay attribution remains sparse. "
                "Skipped Companyfacts, VBB, VCP, state-surface, SEC 8-K, and OHLCV "
                "pattern-name retunes per playbook freeze guidance. This run tests "
                "one free official FINRA short-interest candidate-source variable."
            ),
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
                    "FINRA paper adapter with cached source rows, exact OHLCV "
                    "as-of guards, and parity tests before any daily report or "
                    "live/default behavior changes."
                ),
            },
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production code path is changed. If accepted, promotion "
                    "requires a shared default-off paper adapter and exact "
                    "publication-date/as-of OHLCV parity tests."
                ),
            },
            "interpretation": (
                "The FINRA short-pressure breakout candidate pool cleared Gate 4 "
                "as a default-off replay lead, but no production/shared policy was "
                "promoted."
                if gate4["passed"]
                else (
                    "The FINRA short-pressure breakout candidate pool did not clear "
                    "Gate 4. Do not promote it or retry nearby short-pressure "
                    "breakout thresholds on the same frozen windows without forward "
                    "rows or a stronger borrow-cost/availability field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows or a materially stronger free/cheap "
                "short-pressure field, such as borrow fee, borrow availability, or "
                "float-normalized short interest."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only latest FINRA rows whose publication date is on or before "
        "the signal date plus OHLCV known after the signal-date close; paper entry "
        "is the next available open with production entry slippage; exit is ten "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "finra_short_interest": {
            "source": short_base.FINRA_SOURCE_URL,
            "required_fields": [
                "symbolCode",
                "currentShortPositionQuantity",
                "previousShortPositionQuantity",
                "changePercent",
                "daysToCoverQuantity",
                "averageDailyVolumeQuantity",
            ],
            "rows_loaded": len(finra_context["rows"]),
            "files_attempted": len(finra_context["files"]),
            "files_ok_or_cached": sum(
                1
                for item in finra_context["files"]
                if item.get("status_code") in (200, "cached")
            ),
            "pit_join": "publication_date <= signal_date",
        }
    }
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
            "finra_settlement_date",
            "finra_publication_date",
            "finra_days_to_cover",
            "finra_short_interest",
            "finra_short_interest_change_pct",
            "finra_short_pressure_score",
            "price_prior_high_20d",
            "volume_ratio_20d",
            "rs20_vs_spy",
        ],
    )
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
        framework.base._repo_rel(OUT_JSON),
        framework.base._repo_rel(BEFORE_AGG_JSON),
        framework.base._repo_rel(AFTER_AGG_JSON),
        framework.base._repo_rel(FINRA_ROWS_JSON),
        framework.base._repo_rel(FINRA_FILES_JSON),
        framework.base._repo_rel(LOG_JSON),
        framework.base._repo_rel(TICKET_JSON),
        framework.base._repo_rel(DOC_TICKET_JSON),
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
    return "\n".join(
        [
            "# exp-20260529-017 FINRA Short-Pressure Breakout Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper candidate source using latest published FINRA short-interest pressure plus OHLCV breakout confirmation, top-1 per day, next-open entry, ten-trading-day exit.",
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
    finra_context = _current_finra_context()
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(FINRA_ROWS_JSON, finra_context["rows"])
    framework.base._write_json(FINRA_FILES_JSON, finra_context["files"])
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "FINRA short-pressure breakout candidate pool",
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
