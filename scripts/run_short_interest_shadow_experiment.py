"""Run a default-off FINRA short-interest shadow overlay experiment.

This script is intentionally outside the production signal path. It reads a
backtest result, joins existing entered/skipped candidates to official FINRA
bi-monthly short-interest files using publication-date lag, and writes a small
experiment artifact plus the required docs logs.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

import pandas as pd
import requests

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - outcome metrics can degrade.
    yf = None


REPO_ROOT = Path(__file__).resolve().parents[1]
FINRA_CSV_URL = "https://cdn.finra.org/equity/otcmarket/biweekly/shrt{yyyymmdd}.csv"
FINRA_SOURCE_URL = "https://www.finra.org/finra-data/browse-catalog/equity-short-interest/files"
FINRA_SCHEDULE_URL = (
    "https://www.finra.org/filing-reporting/regulatory-filing-systems/short-interest"
)

US_MARKET_HOLIDAYS = {
    date(2025, 1, 1),
    date(2025, 1, 20),
    date(2025, 2, 17),
    date(2025, 4, 18),
    date(2025, 5, 26),
    date(2025, 6, 19),
    date(2025, 7, 4),
    date(2025, 9, 1),
    date(2025, 11, 27),
    date(2025, 12, 25),
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
}

PUBLICATION_OVERRIDES = {
    date(2025, 11, 14): date(2025, 11, 25),
    date(2025, 11, 28): date(2025, 12, 9),
    date(2025, 12, 15): date(2025, 12, 24),
    date(2025, 12, 31): date(2026, 1, 12),
    date(2026, 1, 15): date(2026, 1, 27),
    date(2026, 1, 30): date(2026, 2, 10),
    date(2026, 2, 13): date(2026, 2, 25),
    date(2026, 2, 27): date(2026, 3, 10),
    date(2026, 3, 13): date(2026, 3, 24),
    date(2026, 3, 31): date(2026, 4, 10),
    date(2026, 4, 15): date(2026, 4, 24),
    date(2026, 4, 30): date(2026, 5, 11),
}

HORIZONS = (5, 10, 20, 60)
SCARCE_SLOT_DECISIONS = {"scarce_slot_breakout_deferred", "slot_sliced"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument(
        "--backtest-result",
        default=str(REPO_ROOT / "data" / "backtest_results_20260505.json"),
    )
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "data" / "experiments"))
    parser.add_argument(
        "--status",
        default="observed_only",
        choices=["observed_only", "rejected", "accepted"],
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def upsert_jsonl(path: Path, payload: Any, key: str = "experiment_id") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[Any] = []
    replaced = False
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    rows.append(raw)
                    continue
                if isinstance(row, dict) and row.get(key) == payload.get(key):
                    rows.append(payload)
                    replaced = True
                else:
                    rows.append(row)
    if not replaced:
        rows.append(payload)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            if isinstance(row, str):
                handle.write(row + "\n")
            else:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def repo_rel(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def to_float(value: Any) -> float | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in US_MARKET_HOLIDAYS


def previous_business_day(day: date) -> date:
    while not is_business_day(day):
        day -= timedelta(days=1)
    return day


def last_business_day(year: int, month: int) -> date:
    if month == 12:
        day = date(year, 12, 31)
    else:
        day = date(year, month + 1, 1) - timedelta(days=1)
    return previous_business_day(day)


def seventh_business_day_after(settlement: date) -> date:
    day = settlement
    count = 0
    while count < 7:
        day += timedelta(days=1)
        if is_business_day(day):
            count += 1
    return day


def publication_date_for(settlement: date) -> tuple[date, str]:
    if settlement in PUBLICATION_OVERRIDES:
        return PUBLICATION_OVERRIDES[settlement], "finra_schedule_override"
    return seventh_business_day_after(settlement), "finra_7th_business_day_rule"


def settlement_dates(start: date, end: date) -> list[date]:
    dates: set[date] = set()
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        dates.add(previous_business_day(date(cursor.year, cursor.month, 15)))
        dates.add(last_business_day(cursor.year, cursor.month))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return sorted(d for d in dates if d <= end)


def metric_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "period": result.get("period"),
        "expected_value_score": result.get("expected_value_score"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "total_pnl": result.get("total_pnl"),
        "sharpe": result.get("sharpe"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
        "vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
        "candidate_count": (result.get("entry_execution_attribution") or {}).get(
            "candidate_events"
        ),
    }


def result_windows(result: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    windows = []
    if isinstance(result.get("primary"), dict):
        windows.append(("primary", result["primary"]))
    else:
        windows.append(("primary", result))
    if isinstance(result.get("secondary"), dict):
        windows.append(("secondary", result["secondary"]))
    return windows


def extract_candidates(result: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for window_name, window in result_windows(result):
        for trade in window.get("trades") or []:
            candidates.append(
                {
                    "window": window_name,
                    "ticker": trade.get("ticker"),
                    "date": trade.get("entry_date"),
                    "strategy": trade.get("strategy"),
                    "decision": "entered",
                    "candidate_type": "entered_trade",
                    "pnl": trade.get("pnl"),
                    "pnl_pct_net": trade.get("pnl_pct_net"),
                    "exit_reason": trade.get("exit_reason"),
                    "exit_date": trade.get("exit_date"),
                    "candidate_rank": None,
                    "available_slots_at_entry_loop": None,
                }
            )
        attribution = window.get("entry_execution_attribution") or {}
        for skipped in attribution.get("sample_skips") or []:
            candidates.append(
                {
                    "window": window_name,
                    "ticker": skipped.get("ticker"),
                    "date": skipped.get("date"),
                    "strategy": skipped.get("strategy"),
                    "decision": skipped.get("decision"),
                    "candidate_type": "skipped_candidate",
                    "pnl": None,
                    "pnl_pct_net": None,
                    "exit_reason": None,
                    "exit_date": None,
                    "candidate_rank": skipped.get("candidate_rank"),
                    "available_slots_at_entry_loop": skipped.get(
                        "available_slots_at_entry_loop"
                    ),
                }
            )
    return [c for c in candidates if c.get("ticker") and c.get("date")]


def candidate_date_ranges(candidates: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    ranges: dict[str, dict[str, str]] = {}
    by_window: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        by_window[candidate["window"]].append(candidate["date"])
    for window, dates in by_window.items():
        ranges[window] = {"start": min(dates), "end": max(dates)}
    return ranges


def fetch_finra_rows(
    tickers: set[str], settlements: list[date]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "ginger-short-interest-shadow/1.0 "
                "(measurement-only; contact repo owner)"
            )
        }
    )
    rows: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for settlement in settlements:
        yyyymmdd = settlement.strftime("%Y%m%d")
        url = FINRA_CSV_URL.format(yyyymmdd=yyyymmdd)
        status = None
        matched = 0
        try:
            response = session.get(url, timeout=30)
            status = response.status_code
            if response.status_code != 200:
                files.append(
                    {
                        "settlement_date": settlement.isoformat(),
                        "url": url,
                        "status_code": response.status_code,
                        "matched_rows": 0,
                    }
                )
                continue
            text = response.content.decode("utf-8-sig")
        except Exception as exc:  # pragma: no cover - network environment varies.
            files.append(
                {
                    "settlement_date": settlement.isoformat(),
                    "url": url,
                    "status_code": status,
                    "error": str(exc),
                    "matched_rows": 0,
                }
            )
            continue
        publication, pub_method = publication_date_for(settlement)
        reader = csv.DictReader(io.StringIO(text), delimiter="|")
        for row in reader:
            ticker = (row.get("symbolCode") or "").upper()
            if ticker not in tickers:
                continue
            matched += 1
            short_interest = to_int(row.get("currentShortPositionQuantity"))
            previous_short_interest = to_int(row.get("previousShortPositionQuantity"))
            rows.append(
                {
                    "ticker": ticker,
                    "settlement_date": settlement.isoformat(),
                    "publication_date": publication.isoformat(),
                    "usable_trade_date": publication.isoformat(),
                    "publication_date_method": pub_method,
                    "pit_safe": True,
                    "short_interest": short_interest,
                    "previous_short_interest": previous_short_interest,
                    "short_interest_change": to_int(row.get("changePreviousNumber")),
                    "short_interest_change_pct": to_float(row.get("changePercent")),
                    "days_to_cover": to_float(row.get("daysToCoverQuantity")),
                    "average_daily_volume": to_int(row.get("averageDailyVolumeQuantity")),
                    "issuer_exchange_code": row.get("issuerServicesGroupExchangeCode"),
                    "market_class_code": row.get("marketClassCode"),
                    "issue_name": row.get("issueName"),
                    "short_interest_float": None,
                    "borrow_fee": None,
                    "shares_available": None,
                    "hard_to_borrow": None,
                    "daily_short_volume": None,
                    "total_volume": None,
                    "daily_short_volume_ratio": None,
                    "source_url": url,
                }
            )
        files.append(
            {
                "settlement_date": settlement.isoformat(),
                "publication_date": publication.isoformat(),
                "url": url,
                "status_code": response.status_code,
                "matched_rows": matched,
            }
        )
    return rows, files


def latest_finra_row(
    ticker_rows: dict[str, list[dict[str, Any]]], ticker: str, candidate_date: date
) -> dict[str, Any] | None:
    rows = ticker_rows.get(ticker.upper()) or []
    eligible = [
        row for row in rows if parse_date(row["publication_date"]) <= candidate_date
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda r: parse_date(r["publication_date"]))


def percentile_scores(values: list[float | None]) -> list[float | None]:
    present = sorted(v for v in values if v is not None and not math.isnan(v))
    if not present:
        return [None for _ in values]
    if len(present) == 1:
        return [0.5 if v is not None else None for v in values]
    scores = []
    denom = len(present) - 1
    for value in values:
        if value is None or math.isnan(value):
            scores.append(None)
            continue
        below_or_equal = sum(1 for v in present if v <= value)
        scores.append(round((below_or_equal - 1) / denom, 4))
    return scores


def download_prices(tickers: list[str], start: date, end: date) -> dict[str, pd.Series]:
    if yf is None:
        return {}
    data = yf.download(
        tickers=tickers,
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    if data is None or len(data) == 0:
        return {}
    prices: dict[str, pd.Series] = {}
    if isinstance(data.columns, pd.MultiIndex):
        for ticker in tickers:
            if ticker in data.columns.get_level_values(0):
                frame = data[ticker]
                if "Close" in frame:
                    prices[ticker] = frame["Close"].dropna()
    elif "Close" in data:
        prices[tickers[0]] = data["Close"].dropna()
    return prices


def forward_return(series: pd.Series, entry_day: date, horizon: int) -> float | None:
    if series.empty:
        return None
    index = pd.DatetimeIndex(series.index).tz_localize(None)
    ordered = pd.Series(series.to_numpy(), index=index).dropna()
    loc = ordered.index.searchsorted(pd.Timestamp(entry_day))
    if loc >= len(ordered):
        return None
    target = loc + horizon
    if target >= len(ordered):
        return None
    start_px = float(ordered.iloc[loc])
    end_px = float(ordered.iloc[target])
    if start_px <= 0:
        return None
    return round(end_px / start_px - 1.0, 6)


def add_forward_returns(candidates: list[dict[str, Any]]) -> str | None:
    tickers = sorted({c["ticker"] for c in candidates})
    dates = [parse_date(c["date"]) for c in candidates]
    if not tickers or not dates:
        return "no_candidates"
    start = min(dates) - timedelta(days=5)
    end = max(dates) + timedelta(days=100)
    try:
        prices = download_prices(tickers, start, end)
    except Exception as exc:  # pragma: no cover - network environment varies.
        for c in candidates:
            c["forward_returns"] = {f"{h}d": None for h in HORIZONS}
        return str(exc)
    for candidate in candidates:
        series = prices.get(candidate["ticker"])
        entry_day = parse_date(candidate["date"])
        candidate["forward_returns"] = {
            f"{h}d": (
                forward_return(series, entry_day, h) if series is not None else None
            )
            for h in HORIZONS
        }
    missing_all = sum(
        1
        for c in candidates
        if all(v is None for v in (c.get("forward_returns") or {}).values())
    )
    return f"missing_all_forward_returns={missing_all}/{len(candidates)}"


def attach_short_tags(
    candidates: list[dict[str, Any]], finra_rows: list[dict[str, Any]]
) -> None:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in finra_rows:
        by_ticker[row["ticker"]].append(row)
    for rows in by_ticker.values():
        rows.sort(key=lambda row: row["publication_date"])

    for candidate in candidates:
        cdate = parse_date(candidate["date"])
        row = latest_finra_row(by_ticker, candidate["ticker"], cdate)
        if row is None:
            candidate["short_interest_tag"] = None
            candidate["pit_safe"] = False
            candidate["short_data_missing_reason"] = "no_published_finra_row_on_or_before_candidate_date"
            continue
        candidate["short_interest_tag"] = {
            key: row.get(key)
            for key in [
                "settlement_date",
                "publication_date",
                "usable_trade_date",
                "publication_date_method",
                "pit_safe",
                "short_interest",
                "previous_short_interest",
                "short_interest_change",
                "short_interest_change_pct",
                "short_interest_float",
                "days_to_cover",
                "average_daily_volume",
                "borrow_fee",
                "shares_available",
                "hard_to_borrow",
                "daily_short_volume",
                "total_volume",
                "daily_short_volume_ratio",
                "source_url",
            ]
        }
        candidate["pit_safe"] = True
        candidate["short_data_missing_reason"] = None

    tagged = [c for c in candidates if c.get("short_interest_tag")]
    crowding_values = [
        (c["short_interest_tag"] or {}).get("days_to_cover") for c in tagged
    ]
    change_values = [
        (c["short_interest_tag"] or {}).get("short_interest_change_pct")
        for c in tagged
    ]
    crowding_scores = percentile_scores(crowding_values)
    change_scores = percentile_scores(change_values)
    for candidate, crowding, change in zip(tagged, crowding_scores, change_scores):
        breakout_flag = 1.0 if candidate.get("strategy") == "breakout_long" else 0.0
        crowding_for_score = 0.0 if crowding is None else crowding
        change_for_score = 0.0 if change is None else change
        setup_score = round(
            min(0.65, 0.5 * crowding_for_score + 0.3 * change_for_score + 0.2 * breakout_flag),
            4,
        )
        tag = candidate["short_interest_tag"]
        tag["short_crowding_score"] = crowding
        tag["short_change_score"] = change
        tag["squeeze_setup_score"] = setup_score
        tag["squeeze_confidence_cap"] = 0.65
        tag["fragile_short_score"] = None
        tag["score_notes"] = [
            "days_to_cover percentile used because short_interest_float is unavailable",
            "borrow pressure unavailable, so squeeze_setup_score is capped at 0.65",
            "fragile_short_score not computed without negative event/news/filing labels",
        ]


def finite_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value: Any = row
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if isinstance(value, (int, float)) and not math.isnan(value):
            values.append(float(value))
    return values


def summarize_returns(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"count": len(rows)}
    for horizon in HORIZONS:
        key = f"forward_returns.{horizon}d"
        values = finite_values(rows, key)
        out[f"forward_{horizon}d_count"] = len(values)
        out[f"forward_{horizon}d_mean"] = round(mean(values), 6) if values else None
        out[f"forward_{horizon}d_median"] = round(median(values), 6) if values else None
    pnl_values = finite_values(rows, "pnl_pct_net")
    out["realized_trade_count"] = len(pnl_values)
    out["realized_pnl_pct_mean"] = round(mean(pnl_values), 6) if pnl_values else None
    out["realized_win_rate"] = (
        round(sum(1 for v in pnl_values if v > 0) / len(pnl_values), 6)
        if pnl_values
        else None
    )
    return out


def build_shadow_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    tagged = [c for c in candidates if c.get("short_interest_tag")]
    scores = finite_values(tagged, "short_interest_tag.short_crowding_score")
    high_threshold = None
    if scores:
        high_threshold = sorted(scores)[max(0, math.ceil(0.75 * len(scores)) - 1)]
    high = [
        c
        for c in tagged
        if high_threshold is not None
        and (c.get("short_interest_tag") or {}).get("short_crowding_score") is not None
        and (c["short_interest_tag"]["short_crowding_score"] >= high_threshold)
    ]
    rest = [c for c in tagged if c not in high]
    breakout = [c for c in tagged if c.get("strategy") == "breakout_long"]
    breakout_high = [c for c in high if c.get("strategy") == "breakout_long"]
    breakout_rest = [c for c in breakout if c not in breakout_high]
    slot_conflicts = [c for c in tagged if c.get("decision") in SCARCE_SLOT_DECISIONS]
    high_slot_conflicts = [c for c in high if c.get("decision") in SCARCE_SLOT_DECISIONS]
    losers = [
        c
        for c in high
        if (c.get("pnl_pct_net") is not None and c["pnl_pct_net"] < 0)
        or ((c.get("forward_returns") or {}).get("20d") is not None and c["forward_returns"]["20d"] < -0.05)
    ]
    high_20 = finite_values(high, "forward_returns.20d")
    rest_20 = finite_values(rest, "forward_returns.20d")
    slot_20 = finite_values(high_slot_conflicts, "forward_returns.20d")
    entered_rest_20 = finite_values(
        [c for c in rest if c.get("decision") == "entered"], "forward_returns.20d"
    )
    return {
        "high_short_definition": {
            "method": "top_quartile_of_tagged_candidate_days_to_cover_percentile",
            "short_crowding_score_threshold": high_threshold,
            "note": "Observation-only threshold for stratification, not a proposed rule.",
        },
        "all_tagged": summarize_returns(tagged),
        "high_short_alone": summarize_returns(high),
        "non_high_short": summarize_returns(rest),
        "high_short_breakout_long": summarize_returns(breakout_high),
        "other_breakout_long": summarize_returns(breakout_rest),
        "high_short_positive_llm_or_news_event": {
            "count": 0,
            "status": "not_testable",
            "reason": "LLM/news positive event labels are not historically replayed in this backtest artifact.",
        },
        "high_short_earnings_or_filing_shock": {
            "count": 0,
            "status": "not_testable",
            "reason": "No PIT event-shock labels joined in this experiment.",
        },
        "slot_conflict_audit": {
            "slot_conflict_count": len(slot_conflicts),
            "high_short_slot_conflict_count": len(high_slot_conflicts),
            "high_short_slot_conflict_forward_20d_mean": (
                round(mean(slot_20), 6) if slot_20 else None
            ),
            "entered_non_high_forward_20d_mean": (
                round(mean(entered_rest_20), 6) if entered_rest_20 else None
            ),
            "scarce_slot_opportunity_cost_20d": (
                round(mean(slot_20) - mean(entered_rest_20), 6)
                if slot_20 and entered_rest_20
                else None
            ),
        },
        "drawdown_false_positive_examples": [
            {
                "window": c.get("window"),
                "date": c.get("date"),
                "ticker": c.get("ticker"),
                "strategy": c.get("strategy"),
                "decision": c.get("decision"),
                "days_to_cover": (c.get("short_interest_tag") or {}).get("days_to_cover"),
                "short_interest_change_pct": (c.get("short_interest_tag") or {}).get(
                    "short_interest_change_pct"
                ),
                "pnl_pct_net": c.get("pnl_pct_net"),
                "forward_20d": (c.get("forward_returns") or {}).get("20d"),
            }
            for c in sorted(
                losers,
                key=lambda c: (
                    c.get("pnl_pct_net")
                    if c.get("pnl_pct_net") is not None
                    else (c.get("forward_returns") or {}).get("20d")
                    or 0
                ),
            )[:8]
        ],
        "delta_observations": {
            "high_minus_non_high_forward_20d": (
                round(mean(high_20) - mean(rest_20), 6)
                if high_20 and rest_20
                else None
            ),
            "expected_value_score_delta": None,
            "reason_ev_delta_null": "No production replay or portfolio ordering change was made.",
        },
    }


def write_audit_markdown(path: Path, payload: dict[str, Any]) -> None:
    coverage = payload["data_coverage"]
    shadow = payload["shadow_metrics"]
    lines = [
        "# Short Interest / Borrow Pressure PIT Coverage + Shadow Experiment",
        "",
        f"- Experiment: `{payload['experiment_id']}`",
        f"- Run timestamp: `{payload['timestamp']}`",
        f"- Source: FINRA official biweekly equity short-interest CSV files",
        f"- Source URLs: `{FINRA_SOURCE_URL}`, `{FINRA_SCHEDULE_URL}`",
        f"- Production impact: `{payload['production_impact']}`",
        f"- Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Data Availability / PIT Status",
        "",
        f"- Candidate rows: `{coverage['candidate_count']}`",
        f"- Tagged candidate rows: `{coverage['tagged_candidate_count']}`",
        f"- PIT-safe tagged rows: `{coverage['pit_safe_tagged_count']}`",
        f"- Coverage: `{coverage['tagged_candidate_coverage_pct']:.2%}`",
        f"- FINRA files fetched: `{coverage['finra_files_ok']}` ok / `{coverage['finra_files_attempted']}` attempted",
        f"- Tickers covered: `{coverage['tickers_covered_count']}` / `{coverage['candidate_ticker_count']}`",
        "- `short_interest_float`: unavailable from FINRA CSV",
        "- `borrow_fee`, `shares_available`, `hard_to_borrow`: unavailable",
        "- `daily_short_volume_ratio`: intentionally not used; daily short volume is activity, not short-interest positioning",
        "",
        "## Shadow Results",
        "",
        f"- High short alone: `{shadow['high_short_alone']}`",
        f"- Non-high short: `{shadow['non_high_short']}`",
        f"- High short + breakout_long: `{shadow['high_short_breakout_long']}`",
        f"- Other breakout_long: `{shadow['other_breakout_long']}`",
        f"- Slot conflict audit: `{shadow['slot_conflict_audit']}`",
        f"- False-positive examples: `{shadow['drawdown_false_positive_examples']}`",
        "",
        "## Decision",
        "",
        payload["decision_reason"],
        "",
        "## Next Minimal Action",
        "",
        payload["next_minimal_action"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def update_ticket(path: Path, payload: dict[str, Any]) -> None:
    ticket = load_json(path)
    ticket["status"] = payload["ticket_status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["single_causal_variable"] = "FINRA_days_to_cover_short_crowding_overlay"
    ticket["result"] = {
        "decision": payload["decision"],
        "production_impact": payload["production_impact"],
        "expected_value_score_delta": None,
        "data_coverage": payload["data_coverage"],
        "artifact": payload["related_files"]["artifact"],
        "audit": payload["related_files"]["audit"],
        "log": payload["related_files"]["log"],
    }
    dump_json(path, ticket)


def update_registry(path: Path, experiment_id: str, status: str) -> None:
    registry = load_json(path)
    registry["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for exp in registry.get("experiments", []):
        if exp.get("experiment_id") == experiment_id:
            exp["status"] = status
            exp["updated_at"] = registry["updated_at"]
            break
    dump_json(path, registry)


def main() -> None:
    args = parse_args()
    experiment_id = args.experiment_id
    result_path = Path(args.backtest_result).resolve()
    result = load_json(result_path)
    candidates = extract_candidates(result)
    if not candidates:
        raise SystemExit("no candidates found in backtest result")

    candidate_tickers = sorted({c["ticker"] for c in candidates})
    candidate_dates = [parse_date(c["date"]) for c in candidates]
    settlements = settlement_dates(
        min(candidate_dates) - timedelta(days=45),
        max(candidate_dates),
    )
    finra_rows, finra_files = fetch_finra_rows(set(candidate_tickers), settlements)
    attach_short_tags(candidates, finra_rows)
    forward_status = add_forward_returns(candidates)
    shadow = build_shadow_summary(candidates)

    tagged = [c for c in candidates if c.get("short_interest_tag")]
    pit_safe = [c for c in tagged if c.get("pit_safe")]
    tickers_covered = sorted({c["ticker"] for c in tagged})
    coverage = {
        "candidate_count": len(candidates),
        "candidate_ticker_count": len(candidate_tickers),
        "candidate_tickers": candidate_tickers,
        "tagged_candidate_count": len(tagged),
        "pit_safe_tagged_count": len(pit_safe),
        "tagged_candidate_coverage_pct": len(tagged) / len(candidates),
        "tickers_covered_count": len(tickers_covered),
        "tickers_covered": tickers_covered,
        "finra_rows_filtered": len(finra_rows),
        "finra_files_attempted": len(finra_files),
        "finra_files_ok": sum(1 for f in finra_files if f.get("status_code") == 200),
        "forward_return_status": forward_status,
    }

    baseline_metrics = {
        window_name: metric_snapshot(window)
        for window_name, window in result_windows(result)
    }
    window_ranges = candidate_date_ranges(candidates)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output_dir = Path(args.output_dir) / experiment_id
    artifact_path = output_dir / "short_interest_shadow_results.json"
    audit_path = (
        REPO_ROOT
        / "docs"
        / "non_ohlcv_data_audit"
        / f"short_interest_borrow_pressure_{experiment_id}_20260505.md"
    )
    log_path = REPO_ROOT / "docs" / "experiments" / "logs" / f"{experiment_id}.json"
    related_files = {
        "artifact": repo_rel(artifact_path),
        "audit": repo_rel(audit_path),
        "log": repo_rel(log_path),
        "backtest_result": repo_rel(result_path),
    }
    hypothesis = (
        "High short-interest crowding is not a standalone long signal; it may add "
        "value only as an overlay on existing breakout/event-confirmed candidates. "
        "Without borrow-fee or float-short data, confidence must be downgraded."
    )
    decision_reason = (
        "Shadow-only: official FINRA short-interest positioning is PIT-safe when "
        "joined by publication date, but this run found no borrow pressure fields, "
        "no float-short field, and only observational candidate stratification. "
        "No production rule or default-off replay is justified yet."
    )
    next_minimal_action = (
        "Add a read-only FINRA adapter/cache that persists settlement_date, "
        "publication_date, usable_trade_date, short_interest, days_to_cover, and "
        "change_percent; then rerun this shadow study on three non-overlapping windows."
    )
    payload = {
        "experiment_id": experiment_id,
        "timestamp": timestamp,
        "status": args.status,
        "ticket_status": args.status,
        "hypothesis": hypothesis,
        "non_ohlcv_data_source": "FINRA official equity short-interest biweekly CSV files",
        "source_urls": [FINRA_SOURCE_URL, FINRA_SCHEDULE_URL],
        "mechanism_family": "short_interest_borrow_pressure_overlay",
        "single_causal_variable": "FINRA_days_to_cover_short_crowding_overlay",
        "data_availability_pit_status": {
            "short_interest": "available_pit_safe_with_publication_date_lag",
            "days_to_cover": "available_pit_safe_with_publication_date_lag",
            "short_interest_change": "available_pit_safe_with_publication_date_lag",
            "short_interest_float": "missing",
            "borrow_fee": "missing",
            "shares_available": "missing",
            "hard_to_borrow": "missing",
            "daily_short_volume_ratio": "not_used_not_positioning",
        },
        "baseline_metrics": baseline_metrics,
        "candidate_date_ranges": window_ranges,
        "data_coverage": coverage,
        "shadow_metrics": shadow,
        "candidate_overlap_and_slot_value": {
            "overlap_with_existing_signals": 1.0,
            "standalone_entries_generated": 0,
            "candidate_count": len(candidates),
            **shadow["slot_conflict_audit"],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
        },
        "decision": "shadow_only",
        "decision_reason": decision_reason,
        "next_minimal_action": next_minimal_action,
        "related_files": related_files,
        "finra_files": finra_files,
        "finra_rows_sample": finra_rows[:20],
        "tagged_candidates": candidates,
    }
    dump_json(artifact_path, payload)

    log_row = {
        "experiment_id": experiment_id,
        "timestamp": timestamp,
        "status": args.status,
        "hypothesis": hypothesis,
        "change_summary": (
            "Ran a default-off FINRA short-interest publication-lag shadow join "
            "against existing entered/skipped candidates; no production code path changed."
        ),
        "change_type": "shadow_non_ohlcv_overlay",
        "component": "scripts/run_short_interest_shadow_experiment.py",
        "parameters": {
            "single_causal_variable": payload["single_causal_variable"],
            "source": "FINRA official biweekly short-interest CSV",
            "publication_lag": "FINRA schedule overrides or 7th business day after settlement",
            "standalone_entries_generated": 0,
            "borrow_pressure_available": False,
        },
        "date_range": {"start": "2025-11-06", "end": "2026-05-05"},
        "secondary_windows": [{"start": "2025-05-07", "end": "2025-11-05"}],
        "market_regime_summary": {
            "primary": "BULL/risk-on per backtester convergence output",
            "secondary": "BULL/risk-on per backtester convergence output",
        },
        "before_metrics": baseline_metrics.get("primary"),
        "after_metrics": baseline_metrics.get("primary"),
        "delta_metrics": {
            "expected_value_score_delta": None,
            "production_portfolio_delta": None,
            "shadow_high_minus_non_high_forward_20d": shadow["delta_observations"][
                "high_minus_non_high_forward_20d"
            ],
        },
        "shadow_metrics": shadow,
        "data_coverage": coverage,
        "llm_metrics": {
            "used_llm": False,
            "positive_event_join_status": "not_testable_without_replayed_positive_event_labels",
        },
        "decision": "shadow_only",
        "rejection_reason": None,
        "next_retry_requires": [
            "Persist FINRA rows locally with publication_date and usable_trade_date",
            "Add float-short or float shares source for short_interest_float",
            "Add paid borrow fee / shares available / hard-to-borrow source",
            "Rerun on three non-overlapping windows before any default-off replay",
        ],
        "related_files": list(related_files.values()),
        "notes": decision_reason,
        "production_impact": payload["production_impact"],
    }
    if "primary" in window_ranges:
        log_row["date_range"] = window_ranges["primary"]
    log_row["secondary_windows"] = [
        window_ranges[name]
        for name in sorted(window_ranges)
        if name != "primary"
    ]
    payload["candidate_date_ranges"] = window_ranges
    dump_json(log_path, log_row)
    upsert_jsonl(REPO_ROOT / "docs" / "experiment_log.jsonl", log_row)
    write_audit_markdown(audit_path, payload)
    update_ticket(
        REPO_ROOT / "docs" / "experiments" / "tickets" / f"{experiment_id}.json",
        payload,
    )
    update_registry(
        REPO_ROOT / "docs" / "experiment_registry.json",
        experiment_id,
        args.status,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
