"""exp-20260503-011 SEC 10-K liquidity shadow universe scout.

Shadow-only second-round replay from exp-20260503-006. This does not add any
tickers to the production/core universe and does not modify the trading path.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from sec_submissions import parse_recent_filings, submission_cache_path  # noqa: E402
from sec_ticker_map import normalize_cik  # noqa: E402
from yfinance_bootstrap import configure_yfinance_runtime  # noqa: E402


EXPERIMENT_ID = "exp-20260503-011"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "sec_10k_liquidity_shadow_scout.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXP006_ARTIFACT = REPO_ROOT / "data" / "experiments" / "exp-20260503-006" / "filing_shadow_universe_scout.json"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

HORIZONS = (5, 10, 20)
LIQUIDITY_BUCKETS = {"adv_5m_20m", "adv_ge_20m"}
MIN_ADV_USD = 5_000_000
MIN_REPLAY_CANDIDATES = 30
MIN_VALID_10D = 20


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def latest_news_path() -> Path:
    paths = sorted(
        path for path in (REPO_ROOT / "data").glob("news_*.json")
        if re.fullmatch(r"news_\d{8}\.json", path.name)
    )
    if not paths:
        raise FileNotFoundError("no news_YYYYMMDD.json archive found")
    return paths[-1]


def _news_date_key(path: Path) -> str:
    return path.stem.replace("news_", "")


def _date_from_archive_item(value: str | None, date_key: str) -> str:
    if value:
        return str(value)[:10]
    return f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"


def _event_key(event: dict[str, Any]) -> str:
    return "|".join([
        str(event.get("ticker") or ""),
        str(event.get("cik") or ""),
        str(event.get("filing_type") or ""),
        str(event.get("accession_number") or event.get("archive_url") or event.get("url") or ""),
        str(event.get("filing_date") or ""),
    ])


def build_latest_sec_pool(news_items: list[dict[str, Any]], *, date_key: str, universe: set[str]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in news_items:
        if item.get("source") != "sec":
            continue
        metadata = item.get("source_metadata") or {}
        filing_type = str(item.get("filing_type") or metadata.get("filing_type") or metadata.get("sec_filing_form") or "").upper()
        if filing_type not in {"8-K", "10-Q", "10-K"} and not filing_type.startswith("10-K"):
            continue
        normalized_type = "10-K" if filing_type.startswith("10-K") else filing_type
        cik = normalize_cik(item.get("sec_cik") or metadata.get("sec_cik"))
        for ticker_raw in item.get("tickers") or []:
            ticker = str(ticker_raw).upper()
            event = {
                "ticker": ticker,
                "cik": cik,
                "filing_type": normalized_type,
                "filing_date": _date_from_archive_item(item.get("published_at"), date_key),
                "accession_number": None,
                "url": item.get("url"),
                "title": item.get("title"),
                "in_current_universe": ticker in universe,
                "source": "latest_news_archive",
            }
            rows.setdefault(_event_key(event), event)
    return sorted(rows.values(), key=lambda row: (row["filing_date"], row["ticker"], row["filing_type"]))


def _read_cached_submission(cik: str) -> dict[str, Any] | None:
    try:
        path = submission_cache_path(cik)
    except ValueError:
        return None
    if not path.exists():
        return None
    return _load_json(path)


def build_historical_10k_events(latest_pool: list[dict[str, Any]], *, max_ciks: int, max_filings_per_cik: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for row in sorted(latest_pool, key=lambda item: item.get("filing_date") or "", reverse=True):
        cik = row.get("cik")
        if not cik or cik in selected:
            continue
        selected[cik] = {"cik": cik, "ticker": row["ticker"], "in_current_universe": row["in_current_universe"]}
        if len(selected) >= max_ciks:
            break

    historical: dict[str, dict[str, Any]] = {}
    cache_missing = []
    for row in selected.values():
        payload = _read_cached_submission(row["cik"])
        if payload is None:
            cache_missing.append(row)
            continue
        filings = parse_recent_filings(
            payload,
            ticker=row["ticker"],
            cik=row["cik"],
            forms={"10-K"},
            max_filings=max_filings_per_cik,
        )
        for event in filings:
            event["in_current_universe"] = bool(row["in_current_universe"])
            historical.setdefault(_event_key(event), event)

    diagnostics = {
        "selected_cik_count": len(selected),
        "cached_submission_count": len(selected) - len(cache_missing),
        "cache_missing_count": len(cache_missing),
        "cache_missing_sample": cache_missing[:20],
    }
    return sorted(historical.values(), key=lambda row: (row["filing_date"], row["ticker"])), diagnostics


def _download_prices(tickers: list[str], start: str, end: str) -> dict[str, list[dict[str, Any]]]:
    import pandas as pd
    import yfinance as yf

    configure_yfinance_runtime()
    prices: dict[str, list[dict[str, Any]]] = {}
    if not tickers:
        return prices

    def store_chunk(chunk: list[str]) -> None:
        request = chunk[0] if len(chunk) == 1 else chunk
        data = yf.download(
            tickers=request,
            start=start,
            end=end,
            progress=False,
            auto_adjust=True,
            group_by="ticker",
            threads=True,
        )
        if data is None or data.empty:
            return
        for ticker in chunk:
            try:
                frame = data[ticker] if isinstance(data.columns, pd.MultiIndex) else data
            except Exception:
                continue
            if frame is None or frame.empty:
                continue
            frame = frame.reset_index()
            rows = []
            for raw in frame.to_dict("records"):
                date_value = raw.get("Date") or raw.get("Datetime")
                close = raw.get("Close")
                volume = raw.get("Volume")
                if date_value is None or pd.isna(close):
                    continue
                rows.append({
                    "date": str(pd.Timestamp(date_value).date()),
                    "close": float(close),
                    "volume": float(volume) if volume is not None and not pd.isna(volume) else None,
                })
            if rows:
                prices[ticker] = rows

    if "SPY" in tickers:
        store_chunk(["SPY"])
    non_spy = [ticker for ticker in tickers if ticker != "SPY"]
    for idx in range(0, len(non_spy), 50):
        store_chunk(non_spy[idx:idx + 50])
    return prices


def _entry_index_after(rows: list[dict[str, Any]], event_date: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] > event_date:
            return idx
    return None


def _avg_dollar_volume(rows: list[dict[str, Any]], entry_idx: int, lookback: int = 20) -> float | None:
    start = max(0, entry_idx - lookback)
    values = []
    for row in rows[start:entry_idx]:
        close = row.get("close")
        volume = row.get("volume")
        if isinstance(close, (int, float)) and isinstance(volume, (int, float)):
            values.append(close * volume)
    return mean(values) if values else None


def liquidity_bucket(avg_dollar_volume: float | None) -> str:
    if avg_dollar_volume is None:
        return "adv_unknown"
    if avg_dollar_volume >= 20_000_000:
        return "adv_ge_20m"
    if avg_dollar_volume >= MIN_ADV_USD:
        return "adv_5m_20m"
    return "adv_lt_5m"


def evaluate_forward_event(
    event: dict[str, Any],
    ticker_rows: list[dict[str, Any]] | None,
    spy_rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    row = dict(event)
    row["horizons"] = {}
    if not ticker_rows:
        row["price_status"] = "no_ticker_price"
        return row
    if not spy_rows:
        row["price_status"] = "no_spy_price"
        return row
    entry_idx = _entry_index_after(ticker_rows, row["filing_date"])
    if entry_idx is None:
        row["price_status"] = "pending_entry"
        return row
    entry_date = ticker_rows[entry_idx]["date"]
    spy_entry_idx = next((idx for idx, spy_row in enumerate(spy_rows) if spy_row["date"] >= entry_date), None)
    if spy_entry_idx is None:
        row["price_status"] = "no_spy_entry"
        return row
    entry_close = ticker_rows[entry_idx].get("close")
    spy_entry_close = spy_rows[spy_entry_idx].get("close")
    if not entry_close or not spy_entry_close:
        row["price_status"] = "bad_entry_price"
        return row

    avg_dv = _avg_dollar_volume(ticker_rows, entry_idx)
    row["entry_date"] = entry_date
    row["entry_close"] = round(entry_close, 4)
    row["avg_dollar_volume_20d"] = round(avg_dv, 2) if avg_dv is not None else None
    row["liquidity_bucket"] = liquidity_bucket(avg_dv)
    row["price_status"] = "covered"
    for horizon in HORIZONS:
        ticker_end_idx = entry_idx + horizon
        spy_end_idx = spy_entry_idx + horizon
        if ticker_end_idx >= len(ticker_rows) or spy_end_idx >= len(spy_rows):
            row["horizons"][f"{horizon}d"] = {"status": "pending"}
            continue
        ticker_ret = ticker_rows[ticker_end_idx]["close"] / entry_close - 1.0
        spy_ret = spy_rows[spy_end_idx]["close"] / spy_entry_close - 1.0
        row["horizons"][f"{horizon}d"] = {
            "status": "valid",
            "return": round(ticker_ret, 6),
            "spy_return": round(spy_ret, 6),
            "excess_return": round(ticker_ret - spy_ret, 6),
            "end_date": ticker_rows[ticker_end_idx]["date"],
        }
    return row


def _snapshot_price_rows(snapshot_path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(snapshot_path)
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        converted = []
        for row in rows:
            date = row.get("Date") or row.get("date")
            close = row.get("Close") or row.get("close")
            volume = row.get("Volume") or row.get("volume")
            if date and close:
                converted.append({"date": str(date)[:10], "close": float(close), "volume": float(volume or 0)})
        if converted:
            out[str(ticker).upper()] = sorted(converted, key=lambda item: item["date"])
    return out


def _horizon_excess_from_rows(
    ticker_rows: list[dict[str, Any]] | None,
    spy_rows: list[dict[str, Any]] | None,
    entry_date: str,
    horizon: int = 10,
) -> float | None:
    if not ticker_rows or not spy_rows:
        return None
    entry_idx = next((idx for idx, row in enumerate(ticker_rows) if row["date"] >= entry_date), None)
    spy_entry_idx = next((idx for idx, row in enumerate(spy_rows) if row["date"] >= entry_date), None)
    if entry_idx is None or spy_entry_idx is None:
        return None
    end_idx = entry_idx + horizon
    spy_end_idx = spy_entry_idx + horizon
    if end_idx >= len(ticker_rows) or spy_end_idx >= len(spy_rows):
        return None
    entry_close = ticker_rows[entry_idx]["close"]
    spy_entry = spy_rows[spy_entry_idx]["close"]
    if not entry_close or not spy_entry:
        return None
    ticker_ret = ticker_rows[end_idx]["close"] / entry_close - 1.0
    spy_ret = spy_rows[spy_end_idx]["close"] / spy_entry - 1.0
    return round(ticker_ret - spy_ret, 6)


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "total_pnl": result.get("total_pnl"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
        "vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
    }


def run_baseline_windows(universe: list[str]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    metrics: dict[str, Any] = {}
    trades: dict[str, list[dict[str, Any]]] = {}
    for label, cfg in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=cfg["start"],
            end=cfg["end"],
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        ).run()
        if "error" in result:
            raise RuntimeError(f"baseline {label} failed: {result['error']}")
        metrics[label] = _metrics(result)
        trades[label] = result.get("trades", [])
    return metrics, trades


def _window_label_for_date(date_value: str) -> str | None:
    for label, cfg in WINDOWS.items():
        if cfg["start"] <= date_value <= cfg["end"]:
            return label
    return None


def _valid_values(rows: list[dict[str, Any]], horizon_key: str, field: str = "excess_return") -> list[float]:
    values = []
    for row in rows:
        data = (row.get("horizons") or {}).get(horizon_key) or {}
        if data.get("status") == "valid" and isinstance(data.get(field), (int, float)):
            values.append(float(data[field]))
    return values


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "avg": None, "median": None, "p25": None, "p75": None, "win_rate": None}
    ordered = sorted(values)
    p25_idx = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.25)))
    p75_idx = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.75)))
    return {
        "count": len(values),
        "avg": round(mean(values), 6),
        "median": round(median(values), 6),
        "p25": round(ordered[p25_idx], 6),
        "p75": round(ordered[p75_idx], 6),
        "win_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
    }


def summarize_forward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        f"{horizon}d": {
            "return": _summary(_valid_values(rows, f"{horizon}d", "return")),
            "excess_return": _summary(_valid_values(rows, f"{horizon}d", "excess_return")),
        }
        for horizon in HORIZONS
    }


def summarize_group(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) if row.get(key) is not None else "unknown")].append(row)
    return {
        group_key: {
            "candidate_count": len(group_rows),
            "forward_distribution": summarize_forward(group_rows),
        }
        for group_key, group_rows in sorted(grouped.items())
    }


def attach_slot_conflict(
    candidates: list[dict[str, Any]],
    baseline_trades: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshot_rows = {
        label: _snapshot_price_rows(REPO_ROOT / cfg["snapshot"])
        for label, cfg in WINDOWS.items()
    }
    core_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for label, trades in baseline_trades.items():
        rows = snapshot_rows[label]
        spy_rows = rows.get("SPY")
        for trade in trades:
            entry_date = str(trade.get("entry_date") or "")[:10]
            ticker = str(trade.get("ticker") or "").upper()
            if not entry_date or not ticker:
                continue
            core_10d_excess = _horizon_excess_from_rows(rows.get(ticker), spy_rows, entry_date, horizon=10)
            core_by_day[entry_date].append({
                "ticker": ticker,
                "strategy": trade.get("strategy"),
                "pnl_pct_net": trade.get("pnl_pct_net"),
                "pnl": trade.get("pnl"),
                "core_10d_excess_return": core_10d_excess,
            })

    enriched = []
    replacement_values = []
    conflict_count = 0
    valid_conflict_count = 0
    positive_count = 0
    for row in candidates:
        candidate = dict(row)
        entry_date = candidate.get("entry_date")
        same_day = core_by_day.get(str(entry_date), [])
        candidate["same_day_core_trade_count"] = len(same_day)
        candidate["slot_conflict_proxy"] = bool(same_day)
        candidate["same_day_core_trades"] = same_day[:5]
        if same_day:
            conflict_count += 1
        core_values = [
            float(item["core_10d_excess_return"])
            for item in same_day
            if isinstance(item.get("core_10d_excess_return"), (int, float))
        ]
        ten_day = (candidate.get("horizons") or {}).get("10d") or {}
        cand_10d = ten_day.get("excess_return") if ten_day.get("status") == "valid" else None
        if core_values and isinstance(cand_10d, (int, float)):
            core_avg = mean(core_values)
            replacement = float(cand_10d) - core_avg
            candidate["same_day_core_avg_10d_excess_return"] = round(core_avg, 6)
            candidate["replacement_value_10d_excess_proxy"] = round(replacement, 6)
            replacement_values.append(replacement)
            valid_conflict_count += 1
            if replacement > 0:
                positive_count += 1
        else:
            candidate["same_day_core_avg_10d_excess_return"] = None
            candidate["replacement_value_10d_excess_proxy"] = None
        enriched.append(candidate)

    summary = {
        "same_day_core_conflict_count": conflict_count,
        "same_day_core_conflict_rate": round(conflict_count / len(candidates), 4) if candidates else None,
        "valid_replacement_proxy_count": valid_conflict_count,
        "positive_replacement_proxy_count": positive_count,
        "positive_replacement_proxy_rate": round(positive_count / valid_conflict_count, 4) if valid_conflict_count else None,
        "replacement_value_10d_excess_proxy": _summary([float(value) for value in replacement_values]),
        "top_positive_replacement_proxy": sorted(
            [
                {
                    "ticker": row["ticker"],
                    "entry_date": row.get("entry_date"),
                    "filing_date": row.get("filing_date"),
                    "liquidity_bucket": row.get("liquidity_bucket"),
                    "candidate_10d_excess_return": (row.get("horizons") or {}).get("10d", {}).get("excess_return"),
                    "replacement_value_10d_excess_proxy": row.get("replacement_value_10d_excess_proxy"),
                    "same_day_core_trades": row.get("same_day_core_trades"),
                }
                for row in enriched
                if isinstance(row.get("replacement_value_10d_excess_proxy"), (int, float))
                and row["replacement_value_10d_excess_proxy"] > 0
            ],
            key=lambda item: item["replacement_value_10d_excess_proxy"],
            reverse=True,
        )[:15],
    }
    return enriched, summary


def _compact_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "cik": row.get("cik"),
        "filing_type": row.get("filing_type"),
        "filing_date": row.get("filing_date"),
        "entry_date": row.get("entry_date"),
        "in_current_universe": row.get("in_current_universe"),
        "price_status": row.get("price_status"),
        "liquidity_bucket": row.get("liquidity_bucket"),
        "avg_dollar_volume_20d": row.get("avg_dollar_volume_20d"),
        "window": row.get("window"),
        "horizons": row.get("horizons"),
        "slot_conflict_proxy": row.get("slot_conflict_proxy"),
        "same_day_core_trade_count": row.get("same_day_core_trade_count"),
        "replacement_value_10d_excess_proxy": row.get("replacement_value_10d_excess_proxy"),
    }


def _safe_float(value: Any) -> Any:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _sanitize(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _sanitize(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_sanitize(value) for value in payload]
    return _safe_float(payload)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    universe = set(get_universe())
    news_path = Path(args.news_path) if args.news_path else latest_news_path()
    date_key = _news_date_key(news_path)
    news_items = _load_json(news_path)
    latest_pool = build_latest_sec_pool(news_items, date_key=date_key, universe=universe)
    latest_10k_pool = [row for row in latest_pool if row["filing_type"] == "10-K"]
    latest_10k_outside = [row for row in latest_10k_pool if not row["in_current_universe"]]

    historical_events, cache_diagnostics = build_historical_10k_events(
        latest_pool,
        max_ciks=args.max_ciks,
        max_filings_per_cik=args.max_filings_per_cik,
    )

    tickers = sorted({event["ticker"] for event in historical_events if event.get("ticker")} | {"SPY"})
    if historical_events:
        min_date = min(event["filing_date"] for event in historical_events)
        start = str(datetime.fromisoformat(min_date).date() - timedelta(days=60))
    else:
        start = "2024-01-01"
    end = str(datetime.now().date() + timedelta(days=1))
    prices = _download_prices(tickers, start=start, end=end)
    spy_rows = prices.get("SPY")
    evaluated = [
        evaluate_forward_event(event, prices.get(event.get("ticker")), spy_rows)
        for event in historical_events
    ]
    price_covered = [row for row in evaluated if row.get("price_status") == "covered"]
    candidate_rows = [
        dict(row, window=_window_label_for_date(row.get("entry_date", "")))
        for row in price_covered
        if not row.get("in_current_universe")
        and row.get("liquidity_bucket") in LIQUIDITY_BUCKETS
        and (row.get("horizons") or {}).get("10d", {}).get("status") == "valid"
    ]
    canonical_candidates = [row for row in candidate_rows if row.get("window")]

    baseline_metrics, baseline_trades = run_baseline_windows(sorted(universe))
    enriched_candidates, slot_summary = attach_slot_conflict(canonical_candidates, baseline_trades)

    valid_10d = _valid_values(candidate_rows, "10d", "excess_return")
    replay_candidate = len(candidate_rows) >= MIN_REPLAY_CANDIDATES and len(valid_10d) >= MIN_VALID_10D
    positive_shadow = bool(valid_10d and mean(valid_10d) > 0)
    decision = "shadow_only"
    status = "shadow_only"
    if not candidate_rows:
        decision = "needs_data_repair"
        status = "coverage_blocked"
    elif replay_candidate and positive_shadow and slot_summary["positive_replacement_proxy_count"] > 0:
        decision = "shadow_only"
        status = "replay_candidate"

    exp006_baseline = {}
    if EXP006_ARTIFACT.exists():
        exp006 = _load_json(EXP006_ARTIFACT)
        exp006_baseline = {
            "decision": exp006.get("decision"),
            "historical_event_count": (exp006.get("historical_sample") or {}).get("historical_event_count"),
            "valid_10d_count": (exp006.get("historical_sample") or {}).get("valid_10d_count"),
            "overall_10d_excess_return": (exp006.get("historical_sample") or {}).get("overall_10d_excess_return"),
            "by_filing_type_10k": ((exp006.get("historical_sample") or {}).get("by_filing_type") or {}).get("10-K"),
            "by_liquidity_adv_5m_20m": ((exp006.get("historical_sample") or {}).get("by_liquidity_bucket") or {}).get("adv_5m_20m"),
            "by_liquidity_adv_ge_20m": ((exp006.get("historical_sample") or {}).get("by_liquidity_bucket") or {}).get("adv_ge_20m"),
        }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "decision": decision,
        "lane": "alpha_discovery",
        "mechanism_family": "new_universe_d_strategy_shadow_scout",
        "change_type": "filing_liquidity_shadow_universe_scout",
        "hypothesis": (
            "Liquidity-gated 10-K filings outside the current production universe may surface "
            "shadow continuation candidates with better forward excess returns and lower slot "
            "conflict than broad SEC filing events, but promotion remains blocked until PIT "
            "eligibility and replacement value are proven."
        ),
        "single_causal_variable": "10-K filing shadow cohort with ADV >= 5M",
        "alpha_hypothesis_category": "new_universe_shadow_entry_source",
        "parameters": {
            "cohort": "Historical SEC 10-K filings from latest mapped SEC archive CIKs",
            "forms": ["10-K"],
            "min_avg_dollar_volume_20d": MIN_ADV_USD,
            "liquidity_buckets": sorted(LIQUIDITY_BUCKETS),
            "max_ciks": args.max_ciks,
            "max_filings_per_cik": args.max_filings_per_cik,
            "forward_horizons": list(HORIZONS),
            "locked_variables": [
                "production universe",
                "trade-enabled tickers",
                "core signal generation",
                "candidate ranking",
                "risk sizing",
                "entries",
                "exits",
                "LLM/news replay",
                "core universe",
                "pilot universe",
            ],
        },
        "allowed_write_scope": [
            "quant/experiments/exp_20260503_011_sec_10k_liquidity_shadow_scout.py",
            "data/experiments/exp-20260503-011",
            "experiments/logs/exp-20260503-011.json",
            "experiments/tickets/exp-20260503-011.json",
            "docs/experiment_log.jsonl",
        ],
        "must_not_touch": [
            "quant/signal_engine.py",
            "quant/risk_engine.py",
            "quant/portfolio_engine.py",
            "quant/run.py",
            "quant/backtester.py",
            "data/universe_registry.json",
            "data/universe_events.jsonl",
        ],
        "history_check": {
            "similar_experiments": {
                "exp-20260503-006": "Filing-driven broad SEC shadow universe scout; broad filing events were not alpha, but 10-K and ADV>=5M buckets justified this second-round shadow replay.",
                "exp-20260503-007": "Semicap equipment static-pool watchlist scout rejected; this run is not raw semicap promotion and remains non-production shadow evidence.",
                "exp-20260503-008": "Pullback RS EOD rank observed-only; this run is event/filing driven rather than pure current-universe OHLCV rank.",
                "exp-20260503-010": "Global RS slot ranking rejected; this run only reports replacement proxy and does not override core slot ordering.",
            },
            "new_evidence": "Uses the exp-20260503-006 discovered discriminators: filing_type=10-K and ADV>=5M, then adds same-day core conflict and replacement-value proxy.",
            "playbook_guardrail": "New universe / new entry remains shadow audit only; promotion is disallowed from static-pool evidence.",
        },
        "baseline_metrics": baseline_metrics,
        "after_metrics": {
            "expected_value_score_delta": 0.0,
            "production_metrics_changed": False,
            "reason": "Shadow-only artifact; no production/core strategy path changed.",
        },
        "expected_value_score_delta": 0.0,
        "coverage": {
            "latest_news_archive": str(news_path.relative_to(REPO_ROOT)),
            "latest_sec_event_count": len(latest_pool),
            "latest_sec_filing_type_counts": dict(Counter(row["filing_type"] for row in latest_pool)),
            "latest_10k_event_count": len(latest_10k_pool),
            "latest_10k_outside_current_universe_count": len(latest_10k_outside),
            "latest_current_universe_overlap": sum(1 for row in latest_pool if row["in_current_universe"]),
            "latest_unique_tickers": len({row["ticker"] for row in latest_pool}),
            **cache_diagnostics,
            "historical_10k_event_count": len(historical_events),
            "historical_unique_tickers": len({row.get("ticker") for row in historical_events if row.get("ticker")}),
            "price_covered_count": len(price_covered),
            "price_coverage_rate": round(len(price_covered) / len(historical_events), 4) if historical_events else None,
            "candidate_count": len(candidate_rows),
            "canonical_window_candidate_count": len(canonical_candidates),
            "valid_5d_count": len(_valid_values(candidate_rows, "5d")),
            "valid_10d_count": len(_valid_values(candidate_rows, "10d")),
            "valid_20d_count": len(_valid_values(candidate_rows, "20d")),
            "candidate_ticker_count": len({row.get("ticker") for row in candidate_rows}),
        },
        "ticker_eligibility": {
            "data_available": bool(candidate_rows),
            "price_data_source": "live yfinance download during experiment; not persisted as production data",
            "sec_data_source": "cached SEC submissions selected from latest mapped SEC archive CIKs",
            "point_in_time_qualified": False,
            "production_trade_enabled": False,
            "survivorship_bias": True,
            "eligibility_note": (
                "Historical submission expansion starts from tickers visible in the latest archive, "
                "so it is research-only static/shadow evidence. It cannot promote a ticker or strategy."
            ),
        },
        "shadow_metrics": {
            "candidate_count": len(candidate_rows),
            "overlap_with_existing_signals": {
                "candidate_tickers_in_current_universe": sum(1 for row in candidate_rows if row.get("in_current_universe")),
                "candidate_tickers_outside_current_universe": sum(1 for row in candidate_rows if not row.get("in_current_universe")),
                "same_day_core_trade_conflict_count": slot_summary["same_day_core_conflict_count"],
                "same_day_core_trade_conflict_rate": slot_summary["same_day_core_conflict_rate"],
            },
            "forward_distribution": summarize_forward(candidate_rows),
            "forward_distribution_canonical_windows": summarize_forward(canonical_candidates),
            "by_window": summarize_group(canonical_candidates, "window"),
            "by_liquidity_bucket": summarize_group(candidate_rows, "liquidity_bucket"),
            "slot_conflict": slot_summary,
            "candidate_samples": [_compact_candidate(row) for row in enriched_candidates[:120]],
        },
        "data_bias_warning": [
            "This is not point-in-time universe evidence; latest SEC archive tickers seed the historical sample.",
            "Historical outside-production ticker price downloads are research inputs, not production snapshots.",
            "Static shadow candidates cannot be promoted to core or pilot without universe ledger eligibility and forward replacement-value evidence.",
            "Same-day slot conflict is only a replacement proxy; it is not a production slot replay.",
        ],
        "promotion_protocol_check": {
            "core_universe_changed": False,
            "trade_enabled_tickers_changed": False,
            "registry_or_ledger_changed": False,
            "promotion_allowed": False,
            "promotion_blocker": "universe_promotion_protocol requires PIT eligibility or live pilot attribution; this run has neither.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_impact": "shadow_only",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "gate4": {
            "passed": False,
            "basis": "Gate 4 is not applicable to promotion because this is shadow-only and changes no strategy logic.",
        },
        "prior_baseline_reference": {
            "exp_20260503_006": exp006_baseline,
        },
        "decision_rationale": (
            "Keep as shadow-only/replay-candidate evidence if coverage and forward returns are usable; "
            "do not promote because PIT eligibility and real replacement value are missing."
            if candidate_rows else
            "Needs data repair: no liquid outside-universe 10-K candidates with valid forward returns were available."
        ),
        "next_action": (
            "Accumulate forward SEC 10-K archives with ticker tags and rerun a default-off PIT shadow replay "
            "that freezes same-day core alternatives before entry."
            if candidate_rows else
            "Repair SEC/price coverage before retrying the 10-K liquidity scout."
        ),
        "related_files": [
            "docs/universe_promotion_protocol.md",
            "docs/universe_governance_rollout_plan.md",
            "data/experiments/exp-20260503-006/filing_shadow_universe_scout.json",
            "quant/experiments/exp_20260503_011_sec_10k_liquidity_shadow_scout.py",
            "data/experiments/exp-20260503-011/sec_10k_liquidity_shadow_scout.json",
            "experiments/logs/exp-20260503-011.json",
            "experiments/tickets/exp-20260503-011.json",
        ],
    }
    return _sanitize(payload)


def persist(payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)

    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {"experiment_id": EXPERIMENT_ID}
    ticket.update({
        "status": payload["status"],
        "decision": payload["decision"],
        "completed_at": payload["timestamp"],
        "result": {
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
            "log": str(LOG_JSON.relative_to(REPO_ROOT)),
            "candidate_count": payload["coverage"]["candidate_count"],
            "canonical_window_candidate_count": payload["coverage"]["canonical_window_candidate_count"],
            "valid_10d_count": payload["coverage"]["valid_10d_count"],
            "same_day_core_trade_conflict_count": payload["shadow_metrics"]["overlap_with_existing_signals"]["same_day_core_trade_conflict_count"],
            "promotion_allowed": False,
            "next_action": payload["next_action"],
        },
    })
    _write_json(TICKET_JSON, ticket)

    compact = dict(payload)
    compact.pop("shadow_metrics", None)
    compact["shadow_metrics_summary"] = {
        "candidate_count": payload["coverage"]["candidate_count"],
        "canonical_window_candidate_count": payload["coverage"]["canonical_window_candidate_count"],
        "forward_distribution": payload["shadow_metrics"]["forward_distribution"],
        "slot_conflict": {
            key: value
            for key, value in payload["shadow_metrics"]["slot_conflict"].items()
            if key != "top_positive_replacement_proxy"
        },
    }
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines() if EXPERIMENT_LOG.exists() else []
    kept_lines = [
        line for line in existing_lines
        if f'"experiment_id":"{EXPERIMENT_ID}"' not in line and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
    ]
    kept_lines.append(json.dumps(compact, ensure_ascii=False, separators=(",", ":")))
    EXPERIMENT_LOG.write_text("\n".join(kept_lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--news-path", default=None)
    parser.add_argument("--max-ciks", type=int, default=120)
    parser.add_argument("--max-filings-per-cik", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    payload = build_payload(parse_args(argv))
    persist(payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "coverage": payload["coverage"],
        "forward_10d_excess": payload["shadow_metrics"]["forward_distribution"]["10d"]["excess_return"],
        "slot_conflict": {
            key: value
            for key, value in payload["shadow_metrics"]["slot_conflict"].items()
            if key != "top_positive_replacement_proxy"
        },
        "promotion_allowed": payload["promotion_protocol_check"]["promotion_allowed"],
    }, indent=2, ensure_ascii=False))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
