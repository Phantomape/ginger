"""exp-20260605-004: SEC FTD + FINRA excluding Form 4 sale pressure.

Alpha search. This replay-only scout tests one independent, free, PIT-visible
ownership-pressure relation on top of the accepted SEC FTD + FINRA candidate
pool: candidates with recent large non-10b5-1 Form 4 sale pressure are excluded
before the daily top-1 paper selection.

Core production signals, ranking, sizing, exits, LLM/news, watchlists, shared
adapters, and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260604_026_sec_ftd_finra_confirmed_candidate_pool as accepted_ftd_finra


EXPERIMENT_ID = "exp-20260605-004"
STEM = "sec_ftd_finra_form4_sale_pressure"
TRIAL_FAMILY = "sec_ftd_finra_ownership_pressure_candidate_pool"
CHANGED_VARIABLE = (
    "sec_ftd_finra_candidate_excludes_recent_large_non10b5_form4_sale_pressure_v1"
)
RULE_VERSION = CHANGED_VARIABLE

BASE_NOTIONAL_USD = accepted_ftd_finra.BASE_NOTIONAL_USD
HOLD_DAYS = accepted_ftd_finra.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = accepted_ftd_finra.MAX_PAPER_TRADES_PER_DAY

MIN_PRICE = accepted_ftd_finra.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20 = accepted_ftd_finra.MIN_AVG_DOLLAR_VOLUME_20
MIN_VOLUME_RATIO_20 = accepted_ftd_finra.MIN_VOLUME_RATIO_20
MIN_CLOSE_LOCATION = accepted_ftd_finra.MIN_CLOSE_LOCATION
MIN_RET20_EXCESS_SPY = accepted_ftd_finra.MIN_RET20_EXCESS_SPY
MIN_FTD_SHARES = accepted_ftd_finra.MIN_FTD_SHARES
MIN_FTD_NOTIONAL = accepted_ftd_finra.MIN_FTD_NOTIONAL
MIN_FTD_NOTIONAL_TO_ADV20 = accepted_ftd_finra.MIN_FTD_NOTIONAL_TO_ADV20
MAX_FTD_PUBLICATION_AGE_DAYS = accepted_ftd_finra.MAX_FTD_PUBLICATION_AGE_DAYS

MIN_FINRA_DAYS_TO_COVER = accepted_ftd_finra.MIN_FINRA_DAYS_TO_COVER
MIN_FINRA_SHORT_INTEREST_CHANGE_PCT = (
    accepted_ftd_finra.MIN_FINRA_SHORT_INTEREST_CHANGE_PCT
)

SALE_LOOKBACK_DAYS = 20
SALE_VALUE_MIN_USD = 500_000.0

MIN_TARGET_TRADES = accepted_ftd_finra.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = accepted_ftd_finra.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = accepted_ftd_finra.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = accepted_ftd_finra.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = accepted_ftd_finra.MAX_POSITIVE_HHI

ROOT = accepted_ftd_finra.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260605_004_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
FTD_ROWS_JSON = OUT_DIR / "sec_ftd_rows_summary.json"
FTD_FILES_JSON = OUT_DIR / "sec_ftd_source_files.json"
FINRA_ROWS_JSON = OUT_DIR / "finra_short_interest_rows_summary.json"
FINRA_FILES_JSON = OUT_DIR / "finra_source_files.json"
FORM4_ROWS_JSON = OUT_DIR / "form4_sale_pressure_rows_summary.json"
FORM4_SOURCE_JSON = OUT_DIR / "form4_source_file.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_COMPARATOR_JSON = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260604-026"
    / "sec_ftd_finra_confirmed_candidate_pool_after_aggregate.json"
)

ftd_base = accepted_ftd_finra.ftd_base
framework = accepted_ftd_finra.framework
_ORIGINAL_BUILD_PAYLOAD = accepted_ftd_finra._ORIGINAL_BUILD_PAYLOAD
_FINRA_CACHE: dict[str, Any] | None = None
_FORM4_CACHE: dict[str, Any] | None = None


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


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _latest_form4_path() -> Path:
    paths = sorted((ROOT / "data" / "non_ohlcv").glob("form4_transactions_*.jsonl"))
    if not paths:
        raise FileNotFoundError("No data/non_ohlcv/form4_transactions_*.jsonl files found")
    return paths[-1]


def _load_sale_pressure_events() -> dict[str, Any]:
    global _FORM4_CACHE
    if _FORM4_CACHE is not None:
        return _FORM4_CACHE

    source_path = _latest_form4_path()
    raw_rows = 0
    qualified_rows = 0
    aggregates: dict[tuple[str, date], dict[str, Any]] = {}
    reject_counts: Counter[str] = Counter()
    by_month: Counter[str] = Counter()
    by_ticker: Counter[str] = Counter()

    with source_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            raw_rows += 1
            row = json.loads(line)
            ticker = str(row.get("ticker") or row.get("issuer_trading_symbol") or "").upper().strip()
            usable_date = _parse_date(row.get("usable_trade_date") or row.get("accepted_at"))
            value = _float(row.get("transaction_value")) or 0.0
            role_flag = any(
                _is_true(row.get(key))
                for key in (
                    "is_officer",
                    "is_director",
                    "is_10pct_owner",
                    "is_ten_percent_owner",
                )
            )

            if not ticker:
                reject_counts["missing_ticker"] += 1
                continue
            if usable_date is None:
                reject_counts["missing_usable_trade_date"] += 1
                continue
            if not _is_true(row.get("pit_safe_flag", True)):
                reject_counts["pit_unsafe"] += 1
                continue
            if str(row.get("table") or "").lower() != "non_derivative":
                reject_counts["not_non_derivative_table"] += 1
                continue
            if str(row.get("transaction_code") or "").upper() != "S":
                reject_counts["not_sale_code"] += 1
                continue
            if str(row.get("acquired_disposed_code") or "").upper() != "D":
                reject_counts["not_disposal"] += 1
                continue
            if _is_true(row.get("10b5_1_flag")):
                reject_counts["rule_10b5_1"] += 1
                continue
            if _is_true(row.get("option_exercise_flag")):
                reject_counts["option_exercise"] += 1
                continue
            if value < SALE_VALUE_MIN_USD:
                reject_counts["below_value_min"] += 1
                continue
            if not role_flag:
                reject_counts["missing_required_role"] += 1
                continue

            qualified_rows += 1
            key = (ticker, usable_date)
            current = aggregates.setdefault(
                key,
                {
                    "ticker": ticker,
                    "date": usable_date,
                    "total_value_usd": 0.0,
                    "transaction_count": 0,
                    "owners": set(),
                    "officer_sale": False,
                    "director_sale": False,
                    "ten_percent_owner_sale": False,
                    "latest_accepted_at": None,
                },
            )
            current["total_value_usd"] += value
            current["transaction_count"] += 1
            owner = str(row.get("owner_name") or row.get("reporting_owner") or "").strip()
            if owner:
                current["owners"].add(owner)
            current["officer_sale"] = current["officer_sale"] or _is_true(row.get("is_officer"))
            current["director_sale"] = current["director_sale"] or _is_true(row.get("is_director"))
            current["ten_percent_owner_sale"] = current["ten_percent_owner_sale"] or any(
                _is_true(row.get(key)) for key in ("is_10pct_owner", "is_ten_percent_owner")
            )
            accepted_at = str(row.get("accepted_at") or "")
            if accepted_at and (
                not current["latest_accepted_at"] or accepted_at > current["latest_accepted_at"]
            ):
                current["latest_accepted_at"] = accepted_at
            by_month[usable_date.isoformat()[:7]] += 1
            by_ticker[ticker] += 1

    by_ticker_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in aggregates.values():
        serializable = {
            **event,
            "date": event["date"],
            "owners": sorted(event["owners"]),
            "owner_count": len(event["owners"]),
        }
        by_ticker_events[event["ticker"]].append(serializable)
    for rows in by_ticker_events.values():
        rows.sort(key=lambda item: item["date"])

    summary = {
        "source": framework._repo_rel(source_path),
        "raw_rows": raw_rows,
        "qualified_rows": qualified_rows,
        "aggregated_event_count": sum(len(rows) for rows in by_ticker_events.values()),
        "qualified_ticker_count": len(by_ticker_events),
        "top_ticker_event_counts": [
            {"ticker": ticker, "row_count": count}
            for ticker, count in by_ticker.most_common(25)
        ],
        "usable_month_counts": dict(sorted(by_month.items())),
        "reject_counts": dict(sorted(reject_counts.items())),
        "filters": {
            "table": "non_derivative",
            "transaction_code": "S",
            "acquired_disposed_code": "D",
            "pit_safe_flag": True,
            "10b5_1_flag": False,
            "option_exercise_flag": False,
            "transaction_value_min_usd": SALE_VALUE_MIN_USD,
            "role_required": "officer/director/10_percent_owner",
            "lookback_calendar_days": SALE_LOOKBACK_DAYS,
        },
        "pit_policy": (
            "Only rows with usable_trade_date on or before the signal date are "
            "eligible; source snapshot may contain later filings, but later "
            "usable_trade_date rows cannot enter historical signals."
        ),
    }
    _FORM4_CACHE = {
        "source_path": source_path,
        "by_ticker": dict(by_ticker_events),
        "summary": summary,
    }
    return _FORM4_CACHE


def _sale_pressure_payload(ticker: str, signal_date: str) -> dict[str, Any] | None:
    context = _load_sale_pressure_events()
    as_of_date = _parse_date(signal_date)
    if as_of_date is None:
        return None
    start = as_of_date - timedelta(days=SALE_LOOKBACK_DAYS)
    events: list[dict[str, Any]] = []
    for event in context["by_ticker"].get(str(ticker).upper(), []):
        event_date = event["date"]
        if start <= event_date <= as_of_date:
            events.append(event)
        if event_date > as_of_date:
            break
    if not events:
        return None

    owners = sorted({owner for event in events for owner in event["owners"]})
    return {
        "recent_form4_sale_pressure_present": True,
        "lookback_days": SALE_LOOKBACK_DAYS,
        "event_count": len(events),
        "transaction_count": sum(int(event["transaction_count"]) for event in events),
        "owner_count": len(owners),
        "total_value_usd": framework._round(
            sum(float(event["total_value_usd"]) for event in events),
            2,
        ),
        "latest_event_date": max(event["date"] for event in events).isoformat(),
        "officer_sale": any(event["officer_sale"] for event in events),
        "director_sale": any(event["director_sale"] for event in events),
        "ten_percent_owner_sale": any(event["ten_percent_owner_sale"] for event in events),
        "events": [
            {
                "date": event["date"].isoformat(),
                "total_value_usd": framework._round(event["total_value_usd"], 2),
                "transaction_count": event["transaction_count"],
                "owner_count": event["owner_count"],
                "latest_accepted_at": event.get("latest_accepted_at"),
            }
            for event in events
        ],
    }


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
    rows, files = accepted_ftd_finra.fetch_finra_short_interest_rows(
        tickers=set(tickers),
        as_of=last.isoformat(),
        lookback_days=lookback_days,
        cache_dir=cache_dir,
    )
    _FINRA_CACHE = {
        "tickers": tickers,
        "rows": rows,
        "files": files,
        "rows_by_ticker": accepted_ftd_finra._finra_rows_by_ticker(rows),
        "lookback_days": lookback_days,
        "source": "official FINRA equity short-interest files",
    }
    return _FINRA_CACHE


def _finra_rows_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return accepted_ftd_finra._finra_rows_summary(rows)


def _latest_finra_row(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    return accepted_ftd_finra._latest_finra_row(rows_by_ticker, ticker, signal_date)


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
    ftd_context = ftd_base._fetch_ftd_context(universe)
    finra_context = _fetch_finra_context(universe)
    ftd_rows_by_ticker = ftd_context["rows_by_ticker"]
    finra_rows_by_ticker = finra_context["rows_by_ticker"]
    core_entries = framework.base.shadow._baseline_entries(before_result)
    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    raw_pass_counts: Counter[str] = Counter()
    reject_counts: Counter[str] = Counter()
    sale_reject_examples: list[dict[str, Any]] = []
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
            pos = pos_by_date[asof]
            if pos + HOLD_DAYS >= len(fr.index) or pos + 1 >= len(fr.index):
                continue
            if asof not in spy.index:
                continue
            signal_date = str(asof.date())
            ftd = ftd_base._latest_ftd_row(ftd_rows_by_ticker, ticker, signal_date)
            if ftd is None:
                continue
            publication_age = (
                datetime.strptime(signal_date, "%Y-%m-%d").date()
                - datetime.strptime(str(ftd["publication_date"]), "%Y-%m-%d").date()
            ).days
            if publication_age < 0 or publication_age > MAX_FTD_PUBLICATION_AGE_DAYS:
                continue
            raw_pass_counts["ftd_publication_lag_passed"] += 1

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
                "ftd_shares": float(ftd["ftd_shares"]),
                "ftd_notional": float(ftd["ftd_notional"]),
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
            if values["ftd_shares"] < MIN_FTD_SHARES:
                continue
            if values["ftd_notional"] < MIN_FTD_NOTIONAL:
                continue
            ftd_to_adv20 = values["ftd_notional"] / values["avg_dollar_volume_20"]
            if ftd_to_adv20 < MIN_FTD_NOTIONAL_TO_ADV20:
                continue
            raw_pass_counts["ftd_pressure_passed"] += 1

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

            sale_pressure = _sale_pressure_payload(ticker, signal_date)
            if sale_pressure is not None:
                reject_counts["recent_large_non10b5_form4_sale_pressure"] += 1
                if len(sale_reject_examples) < 25:
                    sale_reject_examples.append(
                        {
                            "ticker": ticker,
                            "date": signal_date,
                            "ftd_notional_to_adv20": framework._round(ftd_to_adv20, 6),
                            "finra_days_to_cover": framework._round(days_to_cover, 6),
                            "finra_short_interest_change_pct": framework._round(
                                short_change_pct,
                                6,
                            ),
                            "form4_sale_pressure": sale_pressure,
                        }
                    )
                continue
            raw_pass_counts["form4_sale_pressure_exclusion_passed"] += 1

            same_day_core = core_entries.get(signal_date, [])
            if any(str(entry.get("ticker") or "").upper() == ticker for entry in same_day_core):
                continue
            score = (
                math.log1p(values["ftd_notional"]) * 0.45
                + min(ftd_to_adv20, 0.08) * 100.0
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
                "ftd_publication_date": ftd["publication_date"],
                "ftd_settlement_date": ftd["settlement_date"],
                "ftd_publication_age_days": publication_age,
                "ftd_shares": int(values["ftd_shares"]),
                "ftd_notional": framework._round(values["ftd_notional"], 2),
                "ftd_notional_to_adv20": framework._round(ftd_to_adv20, 6),
                "finra_publication_date": finra.get("publication_date"),
                "finra_settlement_date": finra.get("settlement_date"),
                "finra_days_to_cover": framework._round(days_to_cover, 6),
                "finra_short_interest_change_pct": framework._round(
                    short_change_pct,
                    6,
                ),
                "form4_sale_pressure_present": False,
                "form4_sale_pressure_lookback_days": SALE_LOOKBACK_DAYS,
                "form4_sale_pressure_rule_version": RULE_VERSION,
                "avg_dollar_volume_20": framework._round(values["avg_dollar_volume_20"], 2),
                "volume_ratio_20": framework._round(values["volume_ratio_20"], 6),
                "close_location": framework._round(values["close_location"], 6),
                "ret20_excess_spy": framework._round(values["ret20_excess_spy"], 6),
                "same_day_core_entry_count": len(same_day_core),
                "same_ticker_core_overlap": False,
                "source_page": ftd_base.SEC_FTD_PAGE,
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_orders": False,
            }
            if len(finra_examples) < 20:
                finra_examples.append(
                    {
                        "ticker": ticker,
                        "date": signal_date,
                        "ftd_notional_to_adv20": candidate["ftd_notional_to_adv20"],
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
                -float(item["ftd_notional_to_adv20"]),
                -float(item["ret20_excess_spy"]),
                item["ticker"],
            )
        )
        selected.extend(rows[:MAX_PAPER_TRADES_PER_DAY])

    return selected, {
        "raw_pass_counts": dict(raw_pass_counts),
        "reject_counts": dict(sorted(reject_counts.items())),
        "finra_confirmed_examples": finra_examples,
        "form4_sale_pressure_rejected_examples": sale_reject_examples,
        "raw_candidate_count": raw_candidate_count,
        "candidate_day_count": len(candidates_by_date),
    }


def _load_accepted_comparator() -> dict[str, Any]:
    return json.loads(ACCEPTED_COMPARATOR_JSON.read_text(encoding="utf-8"))


def _compare_to_accepted_ftd_finra(payload: dict[str, Any]) -> dict[str, Any]:
    accepted = _load_accepted_comparator()
    windows = accepted["windows"]
    rows: dict[str, dict[str, Any]] = {}
    ev_delta_sum = 0.0
    pnl_delta_sum = 0.0
    ev_regressed = 0
    pnl_regressed = 0
    ev_improved = 0
    pnl_improved = 0
    for label, after in payload["after_metrics"].items():
        base_row = windows[label]
        ev_delta = float(after["expected_value_score"]) - float(
            base_row["expected_value_score"]
        )
        pnl_delta = float(after["total_pnl"]) - float(base_row["total_pnl"])
        ev_delta_sum += ev_delta
        pnl_delta_sum += pnl_delta
        if ev_delta < 0:
            ev_regressed += 1
        elif ev_delta > 0:
            ev_improved += 1
        if pnl_delta < 0:
            pnl_regressed += 1
        elif pnl_delta > 0:
            pnl_improved += 1
        rows[label] = {
            "accepted_ftd_finra_ev": framework._round(base_row["expected_value_score"], 4),
            "after_ev": framework._round(after["expected_value_score"], 4),
            "ev_delta": framework._round(ev_delta, 4),
            "accepted_ftd_finra_total_pnl": framework._round(base_row["total_pnl"], 2),
            "after_total_pnl": framework._round(after["total_pnl"], 2),
            "total_pnl_delta": framework._round(pnl_delta, 2),
            "accepted_ftd_finra_trade_count": base_row.get("trade_count"),
            "after_trade_count": after.get("trade_count"),
        }

    failed: list[str] = []
    if ev_delta_sum <= 0:
        failed.append("accepted_ftd_finra_aggregate_ev_not_improved")
    if pnl_delta_sum <= 0:
        failed.append("accepted_ftd_finra_aggregate_pnl_not_improved")
    if ev_regressed:
        failed.append("accepted_ftd_finra_window_ev_regression")
    if pnl_regressed:
        failed.append("accepted_ftd_finra_window_pnl_regression")

    passed = not failed
    return {
        "comparator_experiment_id": "exp-20260604-026",
        "comparator_artifact": framework._repo_rel(ACCEPTED_COMPARATOR_JSON),
        "passed": passed,
        "failed_gates": failed,
        "aggregate": {
            "accepted_ftd_finra_ev_sum": framework._round(
                accepted["aggregate_expected_value_score"],
                4,
            ),
            "after_ev_sum": framework._round(
                payload["aggregate"]["after_expected_value_score_sum"],
                4,
            ),
            "ev_delta_sum": framework._round(ev_delta_sum, 4),
            "accepted_ftd_finra_total_pnl_sum": framework._round(
                accepted["aggregate_total_pnl"],
                2,
            ),
            "after_total_pnl_sum": framework._round(
                payload["aggregate"]["after_total_pnl_sum"],
                2,
            ),
            "total_pnl_delta_sum": framework._round(pnl_delta_sum, 2),
            "windows_ev_improved": ev_improved,
            "windows_ev_regressed": ev_regressed,
            "windows_pnl_improved": pnl_improved,
            "windows_pnl_regressed": pnl_regressed,
        },
        "window_results": rows,
        "acceptance_standard": (
            "Must improve aggregate EV and PnL versus the accepted FTD+FINRA "
            "comparator with no EV or PnL regressed canonical window."
        ),
    }


def _build_payload() -> dict[str, Any]:
    _patch_framework()
    _load_sale_pressure_events()
    payload = _ORIGINAL_BUILD_PAYLOAD()
    ftd_context = ftd_base._FTD_CACHE or {}
    finra_context = _FINRA_CACHE or {}
    form4_context = _FORM4_CACHE or {}
    form4_summary = form4_context.get("summary", {})

    framework._write_json(FTD_ROWS_JSON, ftd_base._ftd_rows_summary(ftd_context.get("rows", [])))
    framework._write_json(FTD_FILES_JSON, ftd_context.get("files", []))
    framework._write_json(FINRA_ROWS_JSON, _finra_rows_summary(finra_context.get("rows", [])))
    framework._write_json(FINRA_FILES_JSON, finra_context.get("files", []))
    framework._write_json(FORM4_ROWS_JSON, form4_summary)
    framework._write_json(
        FORM4_SOURCE_JSON,
        {
            "source": form4_summary.get("source"),
            "pit_policy": form4_summary.get("pit_policy"),
            "filters": form4_summary.get("filters"),
        },
    )

    accepted_comparator = _compare_to_accepted_ftd_finra(payload)
    original_gate_passed = bool(payload["gate4"]["passed"])
    passed = original_gate_passed and bool(accepted_comparator["passed"])
    merged_failed_gates = list(payload["gate4"]["failed_gates"])
    merged_failed_gates.extend(
        gate
        for gate in accepted_comparator["failed_gates"]
        if gate not in merged_failed_gates
    )

    decision = (
        "positive_replay_lead_not_promoted_requires_ftd_finra_form4_shared_adapter"
        if passed
        else "rejected_sec_ftd_finra_form4_sale_pressure_candidate_pool"
    )
    actual_success = 1 if passed else 0
    ev_delta = payload["aggregate"]["expected_value_score_delta_sum"]
    pnl_delta = payload["aggregate"]["total_pnl_delta_sum"]
    accepted_delta_ev = accepted_comparator["aggregate"]["ev_delta_sum"]
    accepted_delta_pnl = accepted_comparator["aggregate"]["total_pnl_delta_sum"]
    rationale = (
        "Gate 4 passed versus core and the accepted FTD+FINRA comparator, but "
        "this remains replay-only until a shared default-off adapter implements "
        "the same SEC FTD, FINRA, and Form 4 PIT policies in production and "
        "backtest."
        if passed
        else (
            "Gate 4 failed; the Form 4 sale-pressure exclusion did not produce "
            "a clean improvement versus the accepted FTD+FINRA comparator. No "
            "production or shared policy behavior is retained."
        )
    )

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": decision,
            "decision": decision,
            "accepted": passed,
            "hypothesis": (
                "Accepted publication-lagged SEC FTD plus latest PIT FINRA "
                "borrow-pressure candidates may have cleaner replacement value "
                "when rows with recent large non-10b5-1 Form 4 sale pressure "
                "are excluded before daily selection."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": CHANGED_VARIABLE,
            "mechanism_family": "free_sec_settlement_borrow_plus_ownership_pressure",
            "prior_trial_count": 5,
            "nearby_prior_experiments": [
                "exp-20260505-010",
                "exp-20260604-024",
                "exp-20260604-026",
                "exp-20260604-027",
                "exp-20260605-003",
            ],
            "multiple_testing_risk_bucket": "moderate_high",
            "new_evidence_type": "production_visible_sec_form4_ownership_pressure_relation",
            "interpretation": rationale,
            "rejection_reason": None if passed else "; ".join(merged_failed_gates),
            "prediction": {
                "success_probability": 0.28,
                "expected_ev_delta": 0.08,
                "expected_pnl_delta": 1500.0,
                "main_failure_modes": [
                    "underperforms_accepted_ftd_finra_comparator",
                    "thin_sale_pressure_overlap",
                    "late_strong_regression",
                    "concentration_failed",
                ],
                "confidence_reason": (
                    "Accepted FTD+FINRA has strong evidence and Form 4 sales "
                    "are an independent free SEC pressure field, but prior "
                    "simple sale-pressure and FTD/Form4 overlap tests were weak."
                ),
                "recorded_at": "2026-06-05T00:00:00+00:00",
                "actual_success": actual_success,
                "actual_ev_delta_vs_core": ev_delta,
                "actual_pnl_delta_vs_core": pnl_delta,
                "actual_ev_delta_vs_accepted_ftd_finra": accepted_delta_ev,
                "actual_pnl_delta_vs_accepted_ftd_finra": accepted_delta_pnl,
                "brier_score": round((0.28 - actual_success) ** 2, 6),
            },
            "accepted_ftd_finra_comparator": accepted_comparator,
            "sec_ftd_source": {
                "source_page": ftd_base.SEC_FTD_PAGE,
                "row_count": len(ftd_context.get("rows", [])),
                "file_count": len(ftd_context.get("files", [])),
                "rows_artifact": framework._repo_rel(FTD_ROWS_JSON),
                "files_artifact": framework._repo_rel(FTD_FILES_JSON),
                "publication_lag_note": ftd_context.get("publication_lag_note"),
            },
            "finra_source": {
                "source": finra_context.get("source"),
                "row_count": len(finra_context.get("rows", [])),
                "file_count": len(finra_context.get("files", [])),
                "lookback_days": finra_context.get("lookback_days"),
                "rows_artifact": framework._repo_rel(FINRA_ROWS_JSON),
                "files_artifact": framework._repo_rel(FINRA_FILES_JSON),
            },
            "form4_source": {
                "source": form4_summary.get("source"),
                "raw_rows": form4_summary.get("raw_rows"),
                "qualified_rows": form4_summary.get("qualified_rows"),
                "aggregated_event_count": form4_summary.get("aggregated_event_count"),
                "qualified_ticker_count": form4_summary.get("qualified_ticker_count"),
                "rows_artifact": framework._repo_rel(FORM4_ROWS_JSON),
                "source_artifact": framework._repo_rel(FORM4_SOURCE_JSON),
                "pit_policy": form4_summary.get("pit_policy"),
            },
        }
    )
    payload["parameters"].update(
        {
            "single_changed_variable": CHANGED_VARIABLE,
            "source_relation": (
                "Accepted FTD+FINRA candidates are excluded before daily top-1 "
                "selection when the ticker has recent large non-10b5-1 Form 4 "
                "sale pressure by usable_trade_date."
            ),
            "sale_lookback_calendar_days": SALE_LOOKBACK_DAYS,
            "sale_value_min_usd": SALE_VALUE_MIN_USD,
            "form4_filters": form4_summary.get("filters"),
            "comparator_required": "exp-20260604-026 accepted FTD+FINRA after aggregate",
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: accepted SEC FTD + FINRA squeeze setups "
            "should be cleaner when recent large insider sale pressure is absent."
        ),
        "2_history_check": {
            "exp-20260505-010": (
                "Simple Form 4 sale-pressure de-risk failed; this run does not "
                "touch core sizing and only tests ownership pressure inside the "
                "accepted FTD+FINRA replacement candidate pool."
            ),
            "exp-20260604-024": (
                "Form4+FTD purchase overlap was too thin; this run uses sale "
                "pressure as a veto on the already accepted FTD+FINRA pool."
            ),
            "exp-20260604-026/027": (
                "FTD+FINRA candidate route was accepted and promoted as a "
                "default-off shared adapter; this run must beat that accepted "
                "comparator, not only core."
            ),
            "exp-20260605-003": (
                "FTD+Companyfacts was rejected after old_thin regression, so "
                "this run uses a distinct SEC ownership-pressure field."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three windows; positive aggregate "
            "EV/PnL versus core; no EV/PnL-regressed window; sample, drawdown, "
            "survival, and concentration guards pass; additionally improves "
            "aggregate EV/PnL versus accepted FTD+FINRA with no regressed "
            "canonical window."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260605_004_sec_ftd_finra_form4_sale_pressure.py"
        ),
    }
    payload["gate2"].update(
        {
            "minimum_open_position_fields_checked": ["entry_date", "target_price"],
            "ftd_required_fields": [
                "ftd_publication_date",
                "ftd_shares",
                "ftd_notional",
            ],
            "finra_required_fields": [
                "publication_date",
                "days_to_cover",
                "short_interest_change_pct",
            ],
            "form4_required_fields": [
                "usable_trade_date",
                "pit_safe_flag",
                "table",
                "transaction_code",
                "acquired_disposed_code",
                "10b5_1_flag",
                "option_exercise_flag",
                "transaction_value",
                "is_officer/is_director/is_10pct_owner",
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
            "requires_shared_adapter_before_promotion": passed,
        }
    )
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "positive_result_promotion_requirement": (
            "Promotion would require a shared default-off FTD+FINRA+Form4 "
            "adapter and parity tests proving the same publication-date, "
            "usable_trade_date, and source filters in production and backtest."
        ),
        "parity_note": (
            "This runner changes no production path and writes only replay "
            "artifacts. Rejected results retain no production behavior."
        ),
    }
    payload["next_retry_requires"] = (
        "If rejected, do not retune nearby Form 4 sale thresholds or FTD/FINRA "
        "thresholds on the frozen windows without forward replacement rows or "
        "a materially richer ownership-pressure field."
    )
    payload["related_files"] = [
        framework._repo_rel(Path(__file__)),
        framework._repo_rel(OUT_JSON),
        framework._repo_rel(BEFORE_JSON),
        framework._repo_rel(AFTER_JSON),
        framework._repo_rel(FTD_ROWS_JSON),
        framework._repo_rel(FTD_FILES_JSON),
        framework._repo_rel(FINRA_ROWS_JSON),
        framework._repo_rel(FINRA_FILES_JSON),
        framework._repo_rel(FORM4_ROWS_JSON),
        framework._repo_rel(FORM4_SOURCE_JSON),
        framework._repo_rel(LOG_JSON),
        framework._repo_rel(ARTIFACT_MD),
        framework._repo_rel(CARD_MD),
        framework._repo_rel(EXPERIMENT_LOG),
    ]
    payload["gate4"]["passed"] = passed
    payload["gate4"]["decision"] = decision
    payload["gate4"]["rationale"] = rationale
    payload["gate4"]["failed_gates"] = merged_failed_gates
    payload["gate4"]["requires_parity_before_promotion"] = passed
    payload["gate4"]["accepted_ftd_finra_comparator_passed"] = bool(
        accepted_comparator["passed"]
    )
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    gate4 = payload["gate4"]
    target = payload["target_trade_summary"]
    accepted_comp = payload["accepted_ftd_finra_comparator"]
    comp_agg = accepted_comp["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID}: SEC FTD + FINRA Excluding Form 4 Sale Pressure",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV vs core: `{agg['baseline_expected_value_score_sum']}` -> "
        f"`{agg['after_expected_value_score_sum']}` "
        f"({agg['expected_value_score_delta_sum']:+.4f})",
        f"- aggregate PnL delta vs core: `${agg['total_pnl_delta_sum']:+,.2f}`",
        f"- aggregate EV delta vs accepted FTD+FINRA: "
        f"`{comp_agg['ev_delta_sum']:+.4f}`",
        f"- aggregate PnL delta vs accepted FTD+FINRA: "
        f"`${comp_agg['total_pnl_delta_sum']:+,.2f}`",
        f"- target trades: `{target['total_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_pnl_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(gate4['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV core before | EV after | EV delta core | EV delta accepted | PnL delta accepted | target trades |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        comp = accepted_comp["window_results"][label]
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"{comp['ev_delta']:+.4f} | ${comp['total_pnl_delta']:+,.2f} | "
            f"{row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            gate4["rationale"],
            "",
            "This is replay-only/default-off. It uses SEC FTD rows after "
            "publication lag, official FINRA rows after FINRA publication-date "
            "rules, Form 4 rows by usable_trade_date, and same-day/prior OHLCV. "
            "No production entry, ranking, sizing, exit, LLM/news, watchlist, "
            "or order behavior changed.",
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
                "accepted_ftd_finra_comparator": payload[
                    "accepted_ftd_finra_comparator"
                ],
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
