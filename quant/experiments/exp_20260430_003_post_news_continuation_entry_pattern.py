"""exp-20260430-003 post-news continuation shadow audit.

Observed-only alpha discovery. This script does not modify production strategy
logic. The shadow source tests whether archived clean-news items with positive
language, followed by same-day price confirmation, identify useful continuation
candidates outside the existing A/B entry stream.
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


EXPERIMENT_ID = "exp-20260430-003"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "experiments",
    EXPERIMENT_ID,
    "exp_20260430_003_post_news_continuation_entry_pattern.json",
)

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    }),
])

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
FORWARD_DAYS = (5, 10, 20)
MIN_DOLLAR_VOLUME = 25_000_000
MIN_EVENT_DAY_RS_VS_SPY = 0.0
MIN_EVENT_DAY_RETURN = 0.0
MAX_NEWS_LOOKBACK_TRADING_DAYS = 1

EXCLUDED_TICKERS = {
    "GLD", "IAU", "IEF", "IWM", "QQQ", "SLV", "SPY", "TLT",
    "UUP", "USO", "XLE", "XLP", "XLU", "XLV",
}

POSITIVE_RE = re.compile(
    r"\b("
    r"upgrade|upgrades|upgraded|raises|raised|hikes|boost|boosts|beats|beat|"
    r"surge|surges|surged|rally|rallies|rallied|jumps|jumped|pops|popped|"
    r"record|milestone|winner|winners|outperform|outperforms|bullish|"
    r"catalyst|catalysts|strong|growth|approval|launch|partnership"
    r")\b",
    re.IGNORECASE,
)
NEGATIVE_RE = re.compile(
    r"\b("
    r"downgrade|downgrades|downgraded|cuts|cut|trim|trims|trimmed|"
    r"falls|fell|drop|drops|dropped|plunge|plunges|plunged|crash|"
    r"loser|losers|lawsuit|probe|investigation|bearish|warning|miss|misses"
    r")\b",
    re.IGNORECASE,
)


def _load_json(path: str) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_snapshot(snapshot_path: str) -> dict[str, list[dict]]:
    payload = _load_json(os.path.join(REPO_ROOT, snapshot_path))
    return payload.get("ohlcv", payload) if isinstance(payload, dict) else {}


def _date(row: dict) -> str:
    return str(row.get("Date") or row.get("date"))[:10]


def _value(row: dict, key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return float(value)
    return None


def _series(snapshot: dict[str, list[dict]], ticker: str) -> list[dict]:
    return sorted(snapshot.get(ticker) or [], key=_date)


def _row_index(rows: list[dict]) -> dict[str, int]:
    return {_date(row): idx for idx, row in enumerate(rows)}


def _close_return(rows: list[dict], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_close = _value(rows[start_idx], "Close")
    end_close = _value(rows[end_idx], "Close")
    if not start_close or end_close is None:
        return None
    return (end_close / start_close) - 1.0


def _forward_return(rows: list[dict], start_idx: int, horizon: int) -> float | None:
    return _close_return(rows, start_idx, start_idx + horizon)


def _summarize(values: list[float]) -> dict:
    clean = [value for value in values if isinstance(value, (int, float))]
    if not clean:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "win_rate": None,
            "p25": None,
            "p75": None,
        }
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "avg": round(mean(clean), 6),
        "median": round(median(clean), 6),
        "win_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
        "p25": round(ordered[int((len(ordered) - 1) * 0.25)], 6),
        "p75": round(ordered[int((len(ordered) - 1) * 0.75)], 6),
    }


def _run_baseline(universe: list[str], cfg: dict) -> dict:
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


def _metrics(result: dict) -> dict:
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


def _baseline_entries(result: dict) -> dict[str, list[dict]]:
    by_date = defaultdict(list)
    for trade in result.get("trades", []):
        if trade.get("strategy") in {"trend_long", "breakout_long"}:
            by_date[str(trade.get("entry_date"))[:10]].append(trade)
    return by_date


def _trading_dates(snapshot: dict[str, list[dict]]) -> list[str]:
    return [_date(row) for row in _series(snapshot, "SPY")]


def _news_date_from_path(path: str) -> str:
    name = os.path.basename(path)
    return f"{name[11:15]}-{name[15:17]}-{name[17:19]}"


def _news_score(item: dict) -> int:
    text = f"{item.get('title') or ''} {item.get('summary') or ''}"
    return len(POSITIVE_RE.findall(text)) - len(NEGATIVE_RE.findall(text))


def _positive_news_by_ticker() -> dict[str, list[dict]]:
    by_ticker = defaultdict(list)
    data_dir = os.path.join(REPO_ROOT, "data")
    for name in sorted(os.listdir(data_dir)):
        if not (name.startswith("clean_news_") and name.endswith(".json")):
            continue
        path = os.path.join(data_dir, name)
        payload = _load_json(path)
        if not isinstance(payload, list):
            continue
        archive_date = _news_date_from_path(path)
        for item in payload:
            if not isinstance(item, dict):
                continue
            tickers = [str(t).upper() for t in item.get("tickers") or []]
            if not tickers:
                continue
            score = _news_score(item)
            if score <= 0:
                continue
            for ticker in tickers:
                if ticker in EXCLUDED_TICKERS:
                    continue
                by_ticker[ticker].append({
                    "archive_date": archive_date,
                    "published_at": item.get("published_at"),
                    "ticker": ticker,
                    "score": score,
                    "tier": item.get("tier"),
                    "source": item.get("source"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                })
    return by_ticker


def _prior_trading_dates(dates: list[str], idx: int, lookback: int) -> set[str]:
    start = max(0, idx - lookback)
    return set(dates[start: idx + 1])


def _candidate_rows(
    snapshot: dict[str, list[dict]],
    ticker: str,
    dates: list[str],
    news_by_ticker: dict[str, list[dict]],
) -> list[dict]:
    rows = _series(snapshot, ticker)
    if len(rows) < 30:
        return []
    idx_by_date = _row_index(rows)
    spy_rows = _series(snapshot, "SPY")
    spy_idx_by_date = _row_index(spy_rows)
    ticker_news = news_by_ticker.get(ticker, [])
    news_dates = defaultdict(list)
    for item in ticker_news:
        news_dates[item["archive_date"]].append(item)

    out = []
    for date_pos, signal_date in enumerate(dates):
        idx = idx_by_date.get(signal_date)
        spy_idx = spy_idx_by_date.get(signal_date)
        if idx is None or spy_idx is None or idx < 1 or spy_idx < 1:
            continue
        allowed_news_dates = _prior_trading_dates(
            dates,
            date_pos,
            MAX_NEWS_LOOKBACK_TRADING_DAYS,
        )
        matched_news = [
            item
            for allowed_date in allowed_news_dates
            for item in news_dates.get(allowed_date, [])
        ]
        if not matched_news:
            continue

        prev = rows[idx - 1]
        cur = rows[idx]
        cur_close = _value(cur, "Close")
        cur_open = _value(cur, "Open")
        cur_volume = _value(cur, "Volume")
        if cur_close is None or cur_open is None or cur_volume is None:
            continue
        dollar_volume = cur_close * cur_volume
        if dollar_volume < MIN_DOLLAR_VOLUME:
            continue

        event_return = _close_return(rows, idx - 1, idx)
        spy_return = _close_return(spy_rows, spy_idx - 1, spy_idx)
        if event_return is None or spy_return is None:
            continue
        rs_vs_spy = event_return - spy_return
        if event_return < MIN_EVENT_DAY_RETURN:
            continue
        if rs_vs_spy <= MIN_EVENT_DAY_RS_VS_SPY:
            continue
        if cur_close <= cur_open:
            continue

        prev_close = _value(prev, "Close")
        forwards = {
            f"fwd_{horizon}d": _forward_return(rows, idx, horizon)
            for horizon in FORWARD_DAYS
        }
        top_news = sorted(
            matched_news,
            key=lambda item: (-item["score"], str(item.get("published_at"))),
        )[0]
        out.append({
            "date": signal_date,
            "ticker": ticker,
            "sector": SECTOR_MAP.get(ticker, "Unknown"),
            "news_archive_dates": sorted({item["archive_date"] for item in matched_news}),
            "news_count": len(matched_news),
            "max_news_score": max(item["score"] for item in matched_news),
            "top_news_tier": top_news.get("tier"),
            "top_news_title": top_news.get("title"),
            "top_news_url": top_news.get("url"),
            "event_day_return": round(event_return, 6),
            "event_day_spy_return": round(spy_return, 6),
            "event_day_rs_vs_spy": round(rs_vs_spy, 6),
            "close_vs_open": round((cur_close / cur_open) - 1.0, 6) if cur_open else None,
            "close_vs_prev_close": round((cur_close / prev_close) - 1.0, 6) if prev_close else None,
            "dollar_volume": round(dollar_volume, 2),
            **{
                key: round(value, 6) if isinstance(value, float) else None
                for key, value in forwards.items()
            },
        })
    return out


def _evaluate_window(
    label: str,
    cfg: dict,
    universe: list[str],
    news_by_ticker: dict[str, list[dict]],
) -> dict:
    snapshot = _load_snapshot(cfg["snapshot"])
    baseline = _run_baseline(universe, cfg)
    entries_by_date = _baseline_entries(baseline)
    dates = [date for date in _trading_dates(snapshot) if cfg["start"] <= date <= cfg["end"]]

    candidates = []
    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in EXCLUDED_TICKERS:
            continue
        candidates.extend(_candidate_rows(snapshot, ticker, dates, news_by_ticker))

    candidates.sort(
        key=lambda row: (
            row["date"],
            -row["max_news_score"],
            -row["event_day_rs_vs_spy"],
            row["ticker"],
        )
    )
    for row in candidates:
        ab_entries = entries_by_date.get(row["date"], [])
        row["same_day_ab_entry_count"] = len(ab_entries)
        row["same_day_ab_overlap"] = bool(ab_entries)
        row["same_ticker_ab_overlap"] = any(
            trade.get("ticker") == row["ticker"] for trade in ab_entries
        )

    forward_summary = {}
    for horizon in FORWARD_DAYS:
        key = f"fwd_{horizon}d"
        forward_summary[key] = _summarize([
            row[key] for row in candidates if isinstance(row.get(key), (int, float))
        ])

    non_overlap = [row for row in candidates if not row["same_day_ab_overlap"]]
    overlap = [row for row in candidates if row["same_day_ab_overlap"]]
    scarce = {
        "candidate_days": len({row["date"] for row in candidates}),
        "candidate_days_with_ab_entries": len({row["date"] for row in overlap}),
        "same_day_ab_overlap_count": len(overlap),
        "same_day_ab_overlap_rate": round(len(overlap) / len(candidates), 4) if candidates else None,
        "same_ticker_ab_overlap_count": sum(1 for row in candidates if row["same_ticker_ab_overlap"]),
        "avg_ab_entries_on_candidate_day": (
            round(mean([row["same_day_ab_entry_count"] for row in candidates]), 4)
            if candidates else None
        ),
        "candidates_on_ab_collision_days": sum(
            1 for row in candidates if row["same_day_ab_entry_count"] >= 2
        ),
        "fwd_10d_non_overlap": _summarize([
            row["fwd_10d"] for row in non_overlap if isinstance(row.get("fwd_10d"), (int, float))
        ]),
        "fwd_10d_overlap": _summarize([
            row["fwd_10d"] for row in overlap if isinstance(row.get("fwd_10d"), (int, float))
        ]),
    }
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "baseline_metrics": _metrics(baseline),
        "news_archive_dates_in_window": sorted({
            item["archive_date"]
            for items in news_by_ticker.values()
            for item in items
            if cfg["start"] <= item["archive_date"] <= cfg["end"]
        }),
        "candidate_count": len(candidates),
        "candidate_unique_tickers": len({row["ticker"] for row in candidates}),
        "candidate_count_by_sector": dict(sorted(Counter(row["sector"] for row in candidates).items())),
        "top_candidate_tickers": Counter(row["ticker"] for row in candidates).most_common(12),
        "scarce_slot_proxy": scarce,
        "forward_return_distribution": forward_summary,
        "candidates": candidates,
        "sample_candidates": candidates[:40],
    }


def main() -> int:
    universe = get_universe()
    news_by_ticker = _positive_news_by_ticker()
    windows = []
    for label, cfg in WINDOWS.items():
        rec = _evaluate_window(label, cfg, universe, news_by_ticker)
        windows.append(rec)
        fwd10 = rec["forward_return_distribution"]["fwd_10d"]
        print(
            f"[{label}] candidates={rec['candidate_count']} "
            f"tickers={rec['candidate_unique_tickers']} "
            f"overlap={rec['scarce_slot_proxy']['same_day_ab_overlap_rate']} "
            f"fwd10_avg={fwd10['avg']} fwd10_wr={fwd10['win_rate']} "
            f"news_days={len(rec['news_archive_dates_in_window'])}"
        )

    aggregate_fwd10 = []
    aggregate_counts = 0
    aggregate_overlap = 0
    positive_windows = 0
    for window in windows:
        aggregate_counts += window["candidate_count"]
        aggregate_overlap += window["scarce_slot_proxy"]["same_day_ab_overlap_count"]
        fwd10 = window["forward_return_distribution"]["fwd_10d"]
        if fwd10["avg"] is not None and fwd10["avg"] > 0:
            positive_windows += 1
        aggregate_fwd10.extend([
            row["fwd_10d"] for row in window["candidates"]
            if isinstance(row.get("fwd_10d"), (int, float))
        ])

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "A new post-news continuation strategy can provide non-overlapping "
            "candidates for trend/breakout without degrading expected value."
        ),
        "single_causal_variable": "post-news continuation entry pattern",
        "shadow_entry_definition": {
            "news_source": "archived data/clean_news_YYYYMMDD.json only",
            "positive_news_classifier": {
                "positive_keyword_score_must_exceed_negative_keyword_score": True,
                "llm_used": False,
            },
            "filters": {
                "news_lookback_trading_days_including_event_day": MAX_NEWS_LOOKBACK_TRADING_DAYS + 1,
                "event_day_return_min": MIN_EVENT_DAY_RETURN,
                "event_day_rs_vs_spy_min": MIN_EVENT_DAY_RS_VS_SPY,
                "event_day_close_must_be_above_open": True,
                "min_event_day_dollar_volume": MIN_DOLLAR_VOLUME,
            },
            "forward_return_horizons_trading_days": list(FORWARD_DAYS),
        },
        "coverage": {
            "positive_news_tickers": len(news_by_ticker),
            "positive_news_items": sum(len(items) for items in news_by_ticker.values()),
            "archive_date_min": min(
                (item["archive_date"] for items in news_by_ticker.values() for item in items),
                default=None,
            ),
            "archive_date_max": max(
                (item["archive_date"] for items in news_by_ticker.values() for item in items),
                default=None,
            ),
        },
        "windows": windows,
        "aggregate_summary": {
            "candidate_count": aggregate_counts,
            "same_day_ab_overlap_count": aggregate_overlap,
            "same_day_ab_overlap_rate": (
                round(aggregate_overlap / aggregate_counts, 4) if aggregate_counts else None
            ),
            "aggregate_fwd10": _summarize(aggregate_fwd10),
            "positive_fwd10_windows": positive_windows,
        },
        "production_promotion": False,
        "production_promotion_reason": (
            "Shadow-only source audit. The source has no mid_weak or old_thin "
            "coverage with current news archives, and late_strong forward "
            "returns are not positive enough to justify production replay."
        ),
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
