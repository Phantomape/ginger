"""Shadow audit for exp-20260501-012.

This does not change production strategy behavior. It re-tests the previously
observed post-news continuation idea with newer news coverage and the current
accepted stack, then records candidate count, A/B overlap, forward returns, and
a scarce-slot replacement proxy.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from statistics import mean, median


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260501-012"
STEM = "exp_20260501_012_post_news_continuation_entry_pattern"
OUT_JSON = os.path.join(REPO_ROOT, "data", "experiments", EXPERIMENT_ID, f"{STEM}.json")

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
FORWARD_DAYS = (5, 10, 20)
MIN_DOLLAR_VOLUME = 25_000_000
MAX_NEWS_LOOKBACK_TRADING_DAYS = 1

EXCLUDED_TICKERS = {
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "UUP",
    "USO",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}

POSITIVE_RE = re.compile(
    r"\b(upgrade|upgrades|upgraded|raises|raised|hikes|boost|boosts|beats|beat|"
    r"surge|surges|surged|rally|rallies|rallied|jumps|jumped|pops|popped|"
    r"record|milestone|winner|outperform|bullish|catalyst|strong|growth|"
    r"approval|launch|partnership)\b",
    re.IGNORECASE,
)
NEGATIVE_RE = re.compile(
    r"\b(downgrade|downgrades|downgraded|cuts|cut|trim|trims|trimmed|falls|fell|"
    r"drop|drops|dropped|plunge|plunges|plunged|crash|loser|lawsuit|probe|"
    r"investigation|bearish|warning|miss|misses)\b",
    re.IGNORECASE,
)


def load_json(path: str) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_snapshot(snapshot_path: str) -> dict[str, list[dict]]:
    payload = load_json(os.path.join(REPO_ROOT, snapshot_path))
    return payload.get("ohlcv", payload) if isinstance(payload, dict) else {}


def row_date(row: dict) -> str:
    return str(row.get("Date") or row.get("date"))[:10]


def value(row: dict, key: str) -> float | None:
    raw = row.get(key)
    if isinstance(raw, (int, float)) and not math.isnan(float(raw)):
        return float(raw)
    return None


def series(snapshot: dict[str, list[dict]], ticker: str) -> list[dict]:
    return sorted(snapshot.get(ticker) or [], key=row_date)


def row_index(rows: list[dict]) -> dict[str, int]:
    return {row_date(row): idx for idx, row in enumerate(rows)}


def close_return(rows: list[dict], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_close = value(rows[start_idx], "Close")
    end_close = value(rows[end_idx], "Close")
    if not start_close or end_close is None:
        return None
    return (end_close / start_close) - 1.0


def summarize(values: list[float]) -> dict:
    clean = [v for v in values if isinstance(v, (int, float))]
    if not clean:
        return {"count": 0, "avg": None, "median": None, "win_rate": None, "p25": None, "p75": None}
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "avg": round(mean(clean), 6),
        "median": round(median(clean), 6),
        "win_rate": round(sum(1 for v in clean if v > 0) / len(clean), 4),
        "p25": round(ordered[int((len(ordered) - 1) * 0.25)], 6),
        "p75": round(ordered[int((len(ordered) - 1) * 0.75)], 6),
    }


def run_baseline(universe: list[str], cfg: dict) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=BASE_CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    result = engine.run()
    result["expected_value_score"] = compute_expected_value_score(result)
    return result


def metric_snapshot(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "survival_rate": result.get("survival_rate"),
    }


def baseline_entries(result: dict) -> dict[str, list[dict]]:
    by_date = defaultdict(list)
    for trade in result.get("trades", []):
        if trade.get("strategy") in {"trend_long", "breakout_long"}:
            by_date[str(trade.get("entry_date"))[:10]].append(trade)
    return by_date


def trading_dates(snapshot: dict[str, list[dict]]) -> list[str]:
    return [row_date(row) for row in series(snapshot, "SPY")]


def news_date_from_name(name: str) -> str:
    return f"{name[11:15]}-{name[15:17]}-{name[17:19]}"


def news_score(item: dict) -> int:
    text = f"{item.get('title') or ''} {item.get('summary') or ''}"
    return len(POSITIVE_RE.findall(text)) - len(NEGATIVE_RE.findall(text))


def positive_news_by_ticker() -> dict[str, list[dict]]:
    by_ticker = defaultdict(list)
    data_dir = os.path.join(REPO_ROOT, "data")
    for name in sorted(os.listdir(data_dir)):
        if not (name.startswith("clean_news_") and name.endswith(".json")):
            continue
        payload = load_json(os.path.join(data_dir, name))
        if not isinstance(payload, list):
            continue
        archive_date = news_date_from_name(name)
        for item in payload:
            if not isinstance(item, dict):
                continue
            tickers = [str(t).upper() for t in item.get("tickers") or []]
            score = news_score(item)
            if score <= 0:
                continue
            for ticker in tickers:
                if ticker and ticker not in EXCLUDED_TICKERS:
                    by_ticker[ticker].append(
                        {
                            "archive_date": archive_date,
                            "ticker": ticker,
                            "score": score,
                            "tier": item.get("tier"),
                            "published_at": item.get("published_at"),
                            "title": item.get("title"),
                            "url": item.get("url"),
                        }
                    )
    return by_ticker


def lookback_dates(dates: list[str], idx: int) -> set[str]:
    return set(dates[max(0, idx - MAX_NEWS_LOOKBACK_TRADING_DAYS) : idx + 1])


def candidate_rows(snapshot: dict[str, list[dict]], ticker: str, dates: list[str], news: dict) -> list[dict]:
    rows = series(snapshot, ticker)
    spy_rows = series(snapshot, "SPY")
    if len(rows) < 30 or len(spy_rows) < 30:
        return []
    idx_by_date = row_index(rows)
    spy_idx_by_date = row_index(spy_rows)
    news_by_date = defaultdict(list)
    for item in news.get(ticker, []):
        news_by_date[item["archive_date"]].append(item)

    out = []
    for date_pos, signal_date in enumerate(dates):
        idx = idx_by_date.get(signal_date)
        spy_idx = spy_idx_by_date.get(signal_date)
        if idx is None or spy_idx is None or idx < 1 or spy_idx < 1:
            continue
        matched = [item for d in lookback_dates(dates, date_pos) for item in news_by_date.get(d, [])]
        if not matched:
            continue
        cur = rows[idx]
        close = value(cur, "Close")
        open_ = value(cur, "Open")
        volume = value(cur, "Volume")
        if close is None or open_ is None or volume is None:
            continue
        if close <= open_:
            continue
        dollar_volume = close * volume
        if dollar_volume < MIN_DOLLAR_VOLUME:
            continue
        event_ret = close_return(rows, idx - 1, idx)
        spy_ret = close_return(spy_rows, spy_idx - 1, spy_idx)
        if event_ret is None or spy_ret is None:
            continue
        rs_vs_spy = event_ret - spy_ret
        if event_ret < 0 or rs_vs_spy <= 0:
            continue
        top_news = sorted(matched, key=lambda x: (-x["score"], str(x.get("published_at"))))[0]
        record = {
            "date": signal_date,
            "ticker": ticker,
            "sector": SECTOR_MAP.get(ticker, "Unknown"),
            "news_archive_dates": sorted({item["archive_date"] for item in matched}),
            "news_count": len(matched),
            "max_news_score": max(item["score"] for item in matched),
            "top_news_title": top_news.get("title"),
            "top_news_url": top_news.get("url"),
            "event_day_return": round(event_ret, 6),
            "event_day_spy_return": round(spy_ret, 6),
            "event_day_rs_vs_spy": round(rs_vs_spy, 6),
            "close_vs_open": round((close / open_) - 1.0, 6),
            "dollar_volume": round(dollar_volume, 2),
        }
        for horizon in FORWARD_DAYS:
            fwd = close_return(rows, idx, idx + horizon)
            record[f"fwd_{horizon}d"] = round(fwd, 6) if isinstance(fwd, float) else None
        out.append(record)
    return out


def evaluate_window(label: str, cfg: dict, universe: list[str], news: dict) -> dict:
    snapshot = load_snapshot(cfg["snapshot"])
    baseline = run_baseline(universe, cfg)
    entries_by_date = baseline_entries(baseline)
    dates = [d for d in trading_dates(snapshot) if cfg["start"] <= d <= cfg["end"]]
    candidates = []
    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker not in EXCLUDED_TICKERS:
            candidates.extend(candidate_rows(snapshot, ticker, dates, news))

    candidates.sort(key=lambda r: (r["date"], -r["max_news_score"], -r["event_day_rs_vs_spy"], r["ticker"]))
    replacement_deltas = []
    for row in candidates:
        ab_entries = entries_by_date.get(row["date"], [])
        pnl_pcts = [t.get("pnl_pct_net") for t in ab_entries if isinstance(t.get("pnl_pct_net"), (int, float))]
        row["same_day_ab_entry_count"] = len(ab_entries)
        row["same_day_ab_overlap"] = bool(ab_entries)
        row["same_ticker_ab_overlap"] = any(t.get("ticker") == row["ticker"] for t in ab_entries)
        row["same_day_ab_worst_pnl_pct"] = min(pnl_pcts) if pnl_pcts else None
        if isinstance(row.get("fwd_10d"), (int, float)) and pnl_pcts:
            delta = row["fwd_10d"] - min(pnl_pcts)
            replacement_deltas.append(delta)
            row["scarce_slot_replace_worst_ab_delta_10d"] = round(delta, 6)

    fwd = {
        f"fwd_{horizon}d": summarize(
            [row[f"fwd_{horizon}d"] for row in candidates if isinstance(row.get(f"fwd_{horizon}d"), (int, float))]
        )
        for horizon in FORWARD_DAYS
    }
    overlap = [row for row in candidates if row["same_day_ab_overlap"]]
    non_overlap = [row for row in candidates if not row["same_day_ab_overlap"]]
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "baseline_metrics": metric_snapshot(baseline),
        "news_archive_dates_in_window": sorted(
            {
                item["archive_date"]
                for items in news.values()
                for item in items
                if cfg["start"] <= item["archive_date"] <= cfg["end"]
            }
        ),
        "candidate_count": len(candidates),
        "candidate_unique_tickers": len({row["ticker"] for row in candidates}),
        "candidate_count_by_sector": dict(sorted(Counter(row["sector"] for row in candidates).items())),
        "top_candidate_tickers": Counter(row["ticker"] for row in candidates).most_common(12),
        "forward_return_distribution": fwd,
        "scarce_slot_proxy": {
            "candidate_days": len({row["date"] for row in candidates}),
            "same_day_ab_overlap_count": len(overlap),
            "same_day_ab_overlap_rate": round(len(overlap) / len(candidates), 4) if candidates else None,
            "same_ticker_ab_overlap_count": sum(1 for row in candidates if row["same_ticker_ab_overlap"]),
            "fwd_10d_non_overlap": summarize(
                [row["fwd_10d"] for row in non_overlap if isinstance(row.get("fwd_10d"), (int, float))]
            ),
            "fwd_10d_overlap": summarize(
                [row["fwd_10d"] for row in overlap if isinstance(row.get("fwd_10d"), (int, float))]
            ),
            "replace_worst_same_day_ab_delta_10d": summarize(replacement_deltas),
        },
        "sample_candidates": candidates[:50],
    }


def main() -> int:
    universe = get_universe()
    news = positive_news_by_ticker()
    windows = [evaluate_window(label, cfg, universe, news) for label, cfg in WINDOWS.items()]
    all_fwd10 = []
    overlap_count = 0
    candidate_count = 0
    positive_windows = 0
    for window in windows:
        candidate_count += window["candidate_count"]
        overlap_count += window["scarce_slot_proxy"]["same_day_ab_overlap_count"]
        fwd10 = window["forward_return_distribution"]["fwd_10d"]
        if fwd10["avg"] is not None and fwd10["avg"] > 0:
            positive_windows += 1
        all_fwd10.extend(
            row["fwd_10d"]
            for row in window["sample_candidates"]
            if isinstance(row.get("fwd_10d"), (int, float))
        )
        print(
            f"{window['window']}: candidates={window['candidate_count']} "
            f"overlap={window['scarce_slot_proxy']['same_day_ab_overlap_rate']} "
            f"fwd10_avg={fwd10['avg']} fwd10_wr={fwd10['win_rate']} "
            f"news_days={len(window['news_archive_dates_in_window'])}"
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": "Post-news continuation can provide non-overlapping candidates for trend/breakout without degrading expected value.",
        "single_causal_variable": "post-news continuation entry pattern",
        "shadow_entry_definition": {
            "news_source": "archived data/clean_news_YYYYMMDD.json only",
            "llm_used": False,
            "filters": {
                "news_lookback_trading_days_including_event_day": MAX_NEWS_LOOKBACK_TRADING_DAYS + 1,
                "event_day_return_min": 0.0,
                "event_day_rs_vs_spy_min": 0.0,
                "event_day_close_must_be_above_open": True,
                "min_event_day_dollar_volume": MIN_DOLLAR_VOLUME,
            },
            "forward_return_horizons_trading_days": list(FORWARD_DAYS),
        },
        "historical_context": {
            "prior_related_experiment": "exp-20260427-003",
            "why_not_simple_repeat": "New clean_news coverage now extends to 2026-04-30 and accepted-stack baseline changed; this run remains shadow-only and adds a scarce-slot replacement proxy.",
        },
        "coverage": {
            "positive_news_tickers": len(news),
            "positive_news_items": sum(len(items) for items in news.values()),
            "archive_date_min": min((item["archive_date"] for items in news.values() for item in items), default=None),
            "archive_date_max": max((item["archive_date"] for items in news.values() for item in items), default=None),
        },
        "windows": windows,
        "aggregate_summary": {
            "candidate_count": candidate_count,
            "same_day_ab_overlap_count": overlap_count,
            "same_day_ab_overlap_rate": round(overlap_count / candidate_count, 4) if candidate_count else None,
            "sample_limited_aggregate_fwd10": summarize(all_fwd10),
            "positive_fwd10_windows": positive_windows,
        },
        "production_promotion": False,
        "production_promotion_reason": "Shadow audit only; no production entry logic was tested or enabled.",
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
