"""exp-20260604-028: Nasdaq Reg SHO + FINRA candidate-pool scout.

This replay-only alpha search tests one new free, production-visible source:
official NasdaqTrader Reg SHO threshold-list membership, confirmed by the
latest publication-date-safe FINRA short-interest row.

Core signals, ranking, sizing, exits, LLM/news, watchlists, shared adapters,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

import exp_20260604_023_sec_ftd_pressure_breakout_candidate_pool as ftd_base
from finra_iwm_paper_sleeve import (
    _finra_rows_by_ticker,
    fetch_finra_short_interest_rows,
)


EXPERIMENT_ID = "exp-20260604-028"
STEM = "nasdaq_regsho_finra_candidate_pool"
TRIAL_FAMILY = "nasdaq_regsho_finra_confirmed_candidate_pool"
CHANGED_VARIABLE = "nasdaq_regsho_threshold_finra_confirmed_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

BASE_NOTIONAL_USD = ftd_base.BASE_NOTIONAL_USD
HOLD_DAYS = ftd_base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = ftd_base.MAX_PAPER_TRADES_PER_DAY

MIN_PRICE = ftd_base.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20 = ftd_base.MIN_AVG_DOLLAR_VOLUME_20
MIN_VOLUME_RATIO_20 = ftd_base.MIN_VOLUME_RATIO_20
MIN_CLOSE_LOCATION = ftd_base.MIN_CLOSE_LOCATION
MIN_RET20_EXCESS_SPY = ftd_base.MIN_RET20_EXCESS_SPY

MIN_FINRA_DAYS_TO_COVER = 3.0
MIN_FINRA_SHORT_INTEREST_CHANGE_PCT = 0.0

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 2
MAX_DRAWDOWN_WORSE = ftd_base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = ftd_base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = ftd_base.MAX_POSITIVE_HHI

ROOT = ftd_base.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_028_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
REGSHO_ROWS_JSON = OUT_DIR / "nasdaq_regsho_rows_summary.json"
REGSHO_FILES_JSON = OUT_DIR / "nasdaq_regsho_source_files.json"
FINRA_ROWS_JSON = OUT_DIR / "finra_short_interest_rows_summary.json"
FINRA_FILES_JSON = OUT_DIR / "finra_source_files.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

NASDAQ_REGSHO_PAGE = "https://www.nasdaqtrader.com/trader.aspx?id=RegSHOThreshold"
NASDAQ_REGSHO_URL = "https://www.nasdaqtrader.com/dynamic/symdir/regsho/nasdaqth{yyyymmdd}.txt"

framework = ftd_base.framework
_ORIGINAL_BUILD_PAYLOAD = ftd_base._ORIGINAL_BUILD_PAYLOAD
_FINRA_CACHE: dict[str, Any] | None = None
_REGSHO_CACHE: dict[str, Any] | None = None


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


def _float(value: Any) -> float | None:
    try:
        if value in (None, "", "."):
            return None
        out = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _fetch_finra_context(universe: set[str]) -> dict[str, Any]:
    global _FINRA_CACHE
    tickers = sorted(universe.difference(framework.base.shadow.EXCLUDED_TICKERS))
    if _FINRA_CACHE is not None and _FINRA_CACHE.get("tickers") == tickers:
        return _FINRA_CACHE

    starts = [
        datetime.strptime(cfg["start"], "%Y-%m-%d").date()
        for cfg in framework.base.WINDOWS.values()
    ]
    ends = [
        datetime.strptime(cfg["end"], "%Y-%m-%d").date()
        for cfg in framework.base.WINDOWS.values()
    ]
    first = min(starts) - timedelta(days=75)
    last = max(ends)
    lookback_days = max(180, (last - first).days + 30)
    cache_dir = ROOT / "data" / "tmp" / EXPERIMENT_ID / "finra_source_cache"
    rows, files = fetch_finra_short_interest_rows(
        tickers=set(tickers),
        as_of=last.isoformat(),
        lookback_days=lookback_days,
        cache_dir=cache_dir,
    )
    _FINRA_CACHE = {
        "tickers": tickers,
        "rows": rows,
        "files": files,
        "rows_by_ticker": _finra_rows_by_ticker(rows),
        "lookback_days": lookback_days,
        "source": "official FINRA equity short-interest files",
    }
    return _FINRA_CACHE


def _latest_finra_row(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker.upper()) or []
    eligible = [
        row for row in rows if str(row.get("publication_date") or "") <= signal_date
    ]
    if not eligible:
        return None
    return eligible[-1]


def _signal_dates(frames: dict[str, pd.DataFrame]) -> list[str]:
    spy = frames.get("SPY")
    if spy is None:
        raise RuntimeError("SPY is required for canonical trading dates")
    dates: set[str] = set()
    for cfg in framework.base.WINDOWS.values():
        start = pd.Timestamp(cfg["start"])
        end = pd.Timestamp(cfg["end"])
        for asof in spy.loc[start:end].index:
            dates.add(str(asof.date()))
    return sorted(dates)


def _read_regsho_text(
    session: requests.Session,
    signal_date: str,
    cache_dir: Path,
) -> tuple[str | None, dict[str, Any]]:
    yyyymmdd = signal_date.replace("-", "")
    url = NASDAQ_REGSHO_URL.format(yyyymmdd=yyyymmdd)
    cache_path = cache_dir / f"nasdaqth{yyyymmdd}.txt"
    source = "cache"
    status_code: int | str | None = None
    try:
        if cache_path.exists():
            text = cache_path.read_text(encoding="latin-1", errors="replace")
            status_code = "cached"
        else:
            source = "network"
            response = session.get(url, timeout=30)
            status_code = response.status_code
            if response.status_code != 200:
                return None, {
                    "date": signal_date,
                    "url": url,
                    "status_code": status_code,
                    "source": source,
                    "matched_rows": 0,
                }
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(response.content)
            text = response.content.decode("latin-1", errors="replace")
    except Exception as exc:  # pragma: no cover - network can vary.
        return None, {
            "date": signal_date,
            "url": url,
            "status_code": status_code,
            "source": source,
            "error": str(exc),
            "matched_rows": 0,
        }
    return text, {
        "date": signal_date,
        "url": url,
        "status_code": status_code,
        "source": source,
        "cache_path": framework._repo_rel(cache_path),
    }


def _fetch_regsho_context(
    universe: set[str],
    frames: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    global _REGSHO_CACHE
    tickers = sorted(
        universe.difference(framework.base.shadow.EXCLUDED_TICKERS).difference(
            {"SPY", "QQQ", "IWM"}
        )
    )
    dates = _signal_dates(frames)
    cache_key = {"tickers": tickers, "dates": dates}
    if _REGSHO_CACHE is not None and _REGSHO_CACHE.get("cache_key") == cache_key:
        return _REGSHO_CACHE

    ticker_set = set(tickers)
    cache_dir = ROOT / "data" / "tmp" / EXPERIMENT_ID / "nasdaq_regsho_source_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "ginger-nasdaq-regsho-alpha-exp-20260604-028/1.0 "
                "research-only local workspace"
            )
        }
    )

    rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    symbols_by_date: dict[str, set[str]] = {}
    for signal_date in dates:
        text, file_row = _read_regsho_text(session, signal_date, cache_dir)
        if text is None:
            files.append(file_row)
            symbols_by_date[signal_date] = set()
            continue
        parsed = 0
        threshold_rows = 0
        matched = 0
        symbols: set[str] = set()
        first_line = text.splitlines()[0] if text.splitlines() else ""
        if not first_line.startswith("Symbol|"):
            file_row.update(
                {
                    "parsed_rows": 0,
                    "threshold_rows": 0,
                    "matched_rows": 0,
                    "error": "unexpected_nasdaq_regsho_file_header",
                }
            )
            files.append(file_row)
            symbols_by_date[signal_date] = set()
            continue

        reader = csv.DictReader(io.StringIO(text), delimiter="|")
        for raw in reader:
            parsed += 1
            ticker = str(raw.get("Symbol") or "").upper().strip()
            flag = str(raw.get("Reg SHO Threshold Flag") or "").upper().strip()
            if flag != "Y":
                continue
            threshold_rows += 1
            if ticker not in ticker_set:
                continue
            matched += 1
            symbols.add(ticker)
            rows.append(
                {
                    "ticker": ticker,
                    "threshold_date": signal_date,
                    "security_name": str(raw.get("Security Name") or "").strip(),
                    "market_category": str(raw.get("Market Category") or "").strip(),
                    "reg_sho_threshold_flag": flag,
                    "rule_3210": str(raw.get("Rule 3210") or "").strip(),
                    "source_url": file_row["url"],
                    "source_file": file_row.get("cache_path"),
                    "source_page": NASDAQ_REGSHO_PAGE,
                    "known_at_policy": (
                        "signal-date threshold file is used only for next-open "
                        "paper entry, never same-session execution"
                    ),
                }
            )
        file_row.update(
            {
                "parsed_rows": parsed,
                "threshold_rows": threshold_rows,
                "matched_rows": matched,
            }
        )
        files.append(file_row)
        symbols_by_date[signal_date] = symbols

    _REGSHO_CACHE = {
        "cache_key": cache_key,
        "rows": rows,
        "files": files,
        "symbols_by_date": symbols_by_date,
        "source_page": NASDAQ_REGSHO_PAGE,
        "source_note": (
            "Daily NasdaqTrader Reg SHO threshold files are replayed as known "
            "only after the signal-date file and before next-open paper entry; "
            "coverage is Nasdaq threshold securities, not all exchange venues."
        ),
    }
    return _REGSHO_CACHE


def _finra_rows_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_publication_month: Counter[str] = Counter()
    by_ticker: Counter[str] = Counter()
    for row in rows:
        publication = str(row.get("publication_date") or "")
        if len(publication) >= 7:
            by_publication_month[publication[:7]] += 1
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker] += 1
    return {
        "row_count": len(rows),
        "ticker_count": len(by_ticker),
        "publication_month_counts": dict(sorted(by_publication_month.items())),
        "top_ticker_row_counts": [
            {"ticker": ticker, "row_count": count}
            for ticker, count in by_ticker.most_common(25)
        ],
        "note": (
            "Raw FINRA source files are fetched/cached under data/tmp; this "
            "artifact keeps only summary counts for reproducibility."
        ),
    }


def _regsho_rows_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_date: Counter[str] = Counter()
    by_ticker: Counter[str] = Counter()
    by_market_category: Counter[str] = Counter()
    by_rule_3210: Counter[str] = Counter()
    for row in rows:
        date = str(row.get("threshold_date") or "")
        if date:
            by_date[date] += 1
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker] += 1
        category = str(row.get("market_category") or "unknown")
        by_market_category[category] += 1
        rule = str(row.get("rule_3210") or "unknown")
        by_rule_3210[rule] += 1
    return {
        "row_count": len(rows),
        "ticker_count": len(by_ticker),
        "date_count": len(by_date),
        "top_date_counts": [
            {"threshold_date": date, "matched_rows": count}
            for date, count in by_date.most_common(25)
        ],
        "top_ticker_counts": [
            {"ticker": ticker, "row_count": count}
            for ticker, count in by_ticker.most_common(25)
        ],
        "market_category_counts": dict(sorted(by_market_category.items())),
        "rule_3210_counts": dict(sorted(by_rule_3210.items())),
        "source_page": NASDAQ_REGSHO_PAGE,
        "coverage_note": "NasdaqTrader threshold files cover Nasdaq threshold securities only.",
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
    regsho_context = _fetch_regsho_context(universe, frames)
    finra_context = _fetch_finra_context(universe)
    regsho_symbols_by_date = regsho_context["symbols_by_date"]
    finra_rows_by_ticker = finra_context["rows_by_ticker"]
    core_entries = framework.base.shadow._baseline_entries(before_result)
    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    raw_pass_counts: Counter[str] = Counter()
    reject_counts: Counter[str] = Counter()
    finra_examples: list[dict[str, Any]] = []
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
            if ticker not in regsho_symbols_by_date.get(signal_date, set()):
                continue
            raw_pass_counts["nasdaq_regsho_threshold_member"] += 1
            pos = pos_by_date[asof]
            if pos + HOLD_DAYS >= len(fr.index) or pos + 1 >= len(fr.index):
                continue
            if asof not in spy.index:
                continue

            row = fr.loc[asof]
            spy_pos = int(spy.index.get_loc(asof))
            ret20 = framework._ret(closes, pos, 20)
            spy_ret20 = framework._ret(spy_closes, spy_pos, 20)
            values = {
                "close": float(row["Close"]),
                "avg_dollar_volume_20": float(row["avg_dollar_volume_20"]),
                "volume_ratio_20": float(row["volume_ratio_20"]),
                "close_location": float(row["close_location"]),
                "ret20_excess_spy": (
                    ret20 - spy_ret20
                    if ret20 is not None and spy_ret20 is not None
                    else None
                ),
            }
            if any(value is None or not math.isfinite(value) for value in values.values()):
                continue
            raw_pass_counts["fields_non_null"] += 1
            if values["close"] < MIN_PRICE:
                continue
            if values["avg_dollar_volume_20"] < MIN_AVG_DOLLAR_VOLUME_20:
                continue
            raw_pass_counts["liquidity_passed"] += 1
            if bool(row.get("breakout_20")) is not True:
                continue
            raw_pass_counts["breakout_passed"] += 1
            if values["volume_ratio_20"] < MIN_VOLUME_RATIO_20:
                continue
            if values["close_location"] < MIN_CLOSE_LOCATION:
                continue
            if values["ret20_excess_spy"] < MIN_RET20_EXCESS_SPY:
                continue
            raw_pass_counts["price_action_passed"] += 1

            finra = _latest_finra_row(finra_rows_by_ticker, ticker, signal_date)
            if finra is None:
                reject_counts["missing_latest_finra_row"] += 1
                continue
            days_to_cover = _float(finra.get("days_to_cover"))
            short_change_pct = _float(finra.get("short_interest_change_pct"))
            if days_to_cover is None:
                reject_counts["missing_finra_days_to_cover"] += 1
                continue
            if short_change_pct is None:
                reject_counts["missing_finra_short_interest_change_pct"] += 1
                continue
            if days_to_cover < MIN_FINRA_DAYS_TO_COVER:
                reject_counts["finra_days_to_cover_below_threshold"] += 1
                continue
            if short_change_pct <= MIN_FINRA_SHORT_INTEREST_CHANGE_PCT:
                reject_counts["finra_short_interest_change_not_positive"] += 1
                continue
            raw_pass_counts["finra_borrow_pressure_confirmed"] += 1

            same_day_core = core_entries.get(signal_date, [])
            if any(str(entry.get("ticker") or "").upper() == ticker for entry in same_day_core):
                continue
            score = (
                math.log1p(days_to_cover) * 1.35
                + min(short_change_pct, 60.0) / 12.0
                + values["ret20_excess_spy"] * 2.0
                + min(values["volume_ratio_20"], 4.0) * 0.25
                + values["close_location"]
            )
            candidate = {
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "window": label,
                "score": framework._round(score, 6),
                "nasdaq_regsho_threshold_date": signal_date,
                "finra_publication_date": finra.get("publication_date"),
                "finra_settlement_date": finra.get("settlement_date"),
                "finra_days_to_cover": framework._round(days_to_cover, 6),
                "finra_short_interest_change_pct": framework._round(
                    short_change_pct,
                    6,
                ),
                "avg_dollar_volume_20": framework._round(values["avg_dollar_volume_20"], 2),
                "volume_ratio_20": framework._round(values["volume_ratio_20"], 6),
                "close_location": framework._round(values["close_location"], 6),
                "ret20_excess_spy": framework._round(values["ret20_excess_spy"], 6),
                "same_day_core_entry_count": len(same_day_core),
                "same_ticker_core_overlap": False,
                "source_page": NASDAQ_REGSHO_PAGE,
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_orders": False,
            }
            if len(finra_examples) < 20:
                finra_examples.append(
                    {
                        "ticker": ticker,
                        "date": signal_date,
                        "finra_days_to_cover": candidate["finra_days_to_cover"],
                        "finra_short_interest_change_pct": candidate[
                            "finra_short_interest_change_pct"
                        ],
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
                -float(item["finra_days_to_cover"]),
                -float(item["ret20_excess_spy"]),
                item["ticker"],
            )
        )
        selected.extend(rows[:MAX_PAPER_TRADES_PER_DAY])

    return selected, {
        "raw_pass_counts": dict(raw_pass_counts),
        "finra_reject_counts": dict(sorted(reject_counts.items())),
        "finra_confirmed_examples": finra_examples,
        "raw_candidate_count": raw_candidate_count,
        "candidate_day_count": len(candidates_by_date),
    }


def _build_payload() -> dict[str, Any]:
    _patch_framework()
    payload = _ORIGINAL_BUILD_PAYLOAD()
    regsho_context = _REGSHO_CACHE or {}
    finra_context = _FINRA_CACHE or {}
    framework._write_json(REGSHO_ROWS_JSON, _regsho_rows_summary(regsho_context.get("rows", [])))
    framework._write_json(REGSHO_FILES_JSON, regsho_context.get("files", []))
    framework._write_json(FINRA_ROWS_JSON, _finra_rows_summary(finra_context.get("rows", [])))
    framework._write_json(FINRA_FILES_JSON, finra_context.get("files", []))

    passed = bool(payload["gate4"]["passed"])
    decision = (
        "positive_replay_lead_not_promoted_requires_regsho_finra_shared_adapter"
        if passed
        else "rejected_nasdaq_regsho_finra_candidate_pool"
    )
    actual_success = 1 if passed else 0
    ev_delta = payload["aggregate"]["expected_value_score_delta_sum"]
    pnl_delta = payload["aggregate"]["total_pnl_delta_sum"]
    rationale = (
        "Gate 4 passed, but Nasdaq Reg SHO + FINRA remains replay-only until a "
        "shared default-off adapter proves the same PIT source policies in "
        "production and backtest."
        if passed
        else "Gate 4 failed; no production or shared policy behavior is retained."
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": decision,
            "decision": decision,
            "accepted": passed,
            "hypothesis": (
                "Nasdaq Reg SHO threshold-list symbols with latest PIT FINRA "
                "borrow-pressure confirmation may identify cleaner default-off "
                "paper short-pressure breakout candidates."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": CHANGED_VARIABLE,
            "mechanism_family": "free_regsho_threshold_plus_borrow_pressure",
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260604-026",
                "exp-20260604-027",
                "exp-20260604-023",
                "exp-20260603-007",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": (
                "official_nasdaq_regsho_threshold_list_plus_finra_borrow_pressure"
            ),
            "interpretation": rationale,
            "rejection_reason": None if passed else "; ".join(payload["gate4"]["failed_gates"]),
            "prediction": {
                "success_probability": 0.19,
                "expected_ev_delta": 0.08,
                "expected_pnl_delta": 1500.0,
                "main_failure_modes": [
                    "nasdaq_only_coverage",
                    "thin_sample",
                    "late_strong_regression",
                    "underperforms_accepted_ftd_finra",
                    "concentration_failed",
                ],
                "confidence_reason": (
                    "Official daily Nasdaq threshold-list membership is a "
                    "materially different free source, but coverage is "
                    "Nasdaq-only and exp-20260604-026 selected rows had zero "
                    "same-date Nasdaq threshold overlap."
                ),
                "recorded_at": "2026-06-04T23:11:06+00:00",
                "actual_success": actual_success,
                "actual_ev_delta": ev_delta,
                "actual_pnl_delta": pnl_delta,
                "brier_score": round((0.19 - actual_success) ** 2, 6),
            },
            "nasdaq_regsho_source": {
                "source_page": NASDAQ_REGSHO_PAGE,
                "row_count": len(regsho_context.get("rows", [])),
                "file_count": len(regsho_context.get("files", [])),
                "rows_artifact": framework._repo_rel(REGSHO_ROWS_JSON),
                "files_artifact": framework._repo_rel(REGSHO_FILES_JSON),
                "source_note": regsho_context.get("source_note"),
            },
            "finra_source": {
                "source": finra_context.get("source"),
                "row_count": len(finra_context.get("rows", [])),
                "file_count": len(finra_context.get("files", [])),
                "lookback_days": finra_context.get("lookback_days"),
                "rows_artifact": framework._repo_rel(FINRA_ROWS_JSON),
                "files_artifact": framework._repo_rel(FINRA_FILES_JSON),
            },
        }
    )
    payload["parameters"].update(
        {
            "single_changed_variable": CHANGED_VARIABLE,
            "source_relation": (
                "Ticker must be on the official NasdaqTrader Reg SHO threshold "
                "file for signal_date and have the latest publication-date-safe "
                "FINRA row with days_to_cover >= 3.0 and "
                "short_interest_change_pct > 0.0."
            ),
            "nasdaq_regsho_source_page": NASDAQ_REGSHO_PAGE,
            "nasdaq_regsho_file_pattern": NASDAQ_REGSHO_URL,
            "nasdaq_regsho_known_at_policy": (
                "signal-date file used only for next-open paper entry; no "
                "same-session execution"
            ),
            "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
            "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: official Nasdaq threshold-list membership "
            "plus FINRA borrow crowding may identify settlement-stress breakouts "
            "with cleaner continuation value."
        ),
        "2_history_check": {
            "exp-20260604-026": (
                "Accepted SEC FTD + FINRA replay lead; do not retune its "
                "thresholds. This run uses a materially different official "
                "daily threshold-list source."
            ),
            "exp-20260604-027": (
                "Promoted FTD + FINRA into shared default-off adapter; this run "
                "does not change that adapter or any production path."
            ),
            "exp-20260604-023": (
                "Standalone FTD was aggregate positive but late_strong failed."
            ),
            "exp-20260603-007": (
                "FINRA borrow-pressure admission was accepted; this run uses "
                "FINRA only as independent confirmation, not a FINRA retune."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three windows; positive aggregate "
            "EV/PnL; no EV/PnL-regressed window; sample, drawdown, survival, "
            "and concentration guards pass; no production/backtest divergence."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260604_028_nasdaq_regsho_finra_candidate_pool.py"
        ),
    }
    payload["gate2"].update(
        {
            "minimum_open_position_fields_checked": ["entry_date", "target_price"],
            "nasdaq_regsho_required_fields": [
                "Symbol",
                "Reg SHO Threshold Flag",
                "threshold_date",
            ],
            "finra_required_fields": [
                "publication_date",
                "days_to_cover",
                "short_interest_change_pct",
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
            "requires_shared_adapter_before_promotion": passed,
        }
    )
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "parity_note": (
            "This runner changes no production path. A positive result would "
            "remain only a replay lead until the same Reg SHO + FINRA source "
            "policies are implemented in a shared default-off adapter with "
            "parity tests."
        ),
    }
    payload["next_retry_requires"] = (
        "If rejected, do not retune Nasdaq Reg SHO OHLCV/FINRA thresholds on "
        "the frozen windows; require broader exchange threshold coverage, "
        "forward rows, or a genuinely new PIT borrow-cost / loan-availability "
        "field."
    )
    payload["related_files"] = [
        framework._repo_rel(Path(__file__)),
        framework._repo_rel(OUT_JSON),
        framework._repo_rel(BEFORE_JSON),
        framework._repo_rel(AFTER_JSON),
        framework._repo_rel(REGSHO_ROWS_JSON),
        framework._repo_rel(REGSHO_FILES_JSON),
        framework._repo_rel(FINRA_ROWS_JSON),
        framework._repo_rel(FINRA_FILES_JSON),
        framework._repo_rel(LOG_JSON),
        framework._repo_rel(ARTIFACT_MD),
        framework._repo_rel(CARD_MD),
        framework._repo_rel(EXPERIMENT_LOG),
    ]
    payload["gate4"]["decision"] = decision
    payload["gate4"]["rationale"] = rationale
    payload["gate4"]["requires_parity_before_promotion"] = passed
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Nasdaq Reg SHO + FINRA Candidate Pool",
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
            "The tested fields are official NasdaqTrader Reg SHO threshold files "
            "used only for next-open paper entry, official FINRA rows after "
            "publication-date rules, and same-day/prior OHLCV. The result is "
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
            f"${row['paper_pnl_usd']:,.2f} | {row['positive_pnl_share']} |"
        )
    lines.append("")
    return "\n".join(lines)


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
