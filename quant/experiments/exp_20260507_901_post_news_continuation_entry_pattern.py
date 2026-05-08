"""exp-20260507-901 post-news continuation shadow audit.

This observed-only runner retests the same narrow mechanism as the prior
post-news continuation audits: archived positive clean-news headlines followed
by same-day price confirmation. It does not use event_snapshot SEC rows as a
substitute for positive news, and it does not change production strategy code.
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


EXPERIMENT_ID = "exp-20260507-901"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "experiments",
    EXPERIMENT_ID,
    "exp_20260507_901_post_news_continuation_entry_pattern.json",
)

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
MIN_EVENT_DAY_RS_VS_SPY = 0.0
MIN_EVENT_DAY_RETURN = 0.0
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
    r"\b("
    r"upgrade|upgrades|upgraded|raises|raised|hikes|boost|boosts|beats|beat|"
    r"surge|surges|surged|rally|rallies|rallied|jumps|jumped|pops|popped|"
    r"record|milestone|winner|winners|outperform|outperforms|bullish|"
    r"catalyst|catalysts|strong|growth|approval|launch|partnership|"
    r"rebound|recovery|profitability|surprises"
    r")\b",
    re.IGNORECASE,
)
NEGATIVE_RE = re.compile(
    r"\b("
    r"downgrade|downgrades|downgraded|cuts|cut|trim|trims|trimmed|"
    r"falls|fell|drop|drops|dropped|plunge|plunges|plunged|crash|"
    r"loser|losers|lawsuit|probe|investigation|bearish|warning|miss|misses|"
    r"slips|dips|slide"
    r")\b",
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


def forward_return(rows: list[dict], start_idx: int, horizon: int) -> float | None:
    return close_return(rows, start_idx, start_idx + horizon)


def summarize(values: list[float]) -> dict:
    clean = [item for item in values if isinstance(item, (int, float))]
    if not clean:
        return {"count": 0, "avg": None, "median": None, "win_rate": None, "p25": None, "p75": None}
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "avg": round(mean(clean), 6),
        "median": round(median(clean), 6),
        "win_rate": round(sum(1 for item in clean if item > 0) / len(clean), 4),
        "p25": round(ordered[int((len(ordered) - 1) * 0.25)], 6),
        "p75": round(ordered[int((len(ordered) - 1) * 0.75)], 6),
    }


def baseline_result(universe: list[str], cfg: dict) -> dict:
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


def core_metrics(result: dict) -> dict:
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


def clean_news_date_from_path(path: str) -> str:
    name = os.path.basename(path)
    return f"{name[11:15]}-{name[15:17]}-{name[17:19]}"


def clean_news_score(item: dict) -> int:
    text = f"{item.get('title') or ''} {item.get('summary') or ''}"
    return len(POSITIVE_RE.findall(text)) - len(NEGATIVE_RE.findall(text))


def positive_clean_news_by_ticker() -> tuple[dict[str, list[dict]], dict]:
    by_ticker = defaultdict(list)
    archive_files = []
    data_dir = os.path.join(REPO_ROOT, "data")
    for name in sorted(os.listdir(data_dir)):
        if not (name.startswith("clean_news_") and name.endswith(".json")):
            continue
        path = os.path.join(data_dir, name)
        archive_date = clean_news_date_from_path(path)
        payload = load_json(path)
        item_count = len(payload) if isinstance(payload, list) else 0
        archive_files.append({"date": archive_date, "path": os.path.relpath(path, REPO_ROOT), "items": item_count})
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            tickers = [str(ticker).upper() for ticker in item.get("tickers") or []]
            score = clean_news_score(item)
            if not tickers or score <= 0:
                continue
            for ticker in tickers:
                if ticker in EXCLUDED_TICKERS:
                    continue
                by_ticker[ticker].append(
                    {
                        "archive_date": archive_date,
                        "published_at": item.get("published_at"),
                        "ticker": ticker,
                        "score": score,
                        "tier": item.get("tier"),
                        "source": item.get("source"),
                        "title": item.get("title"),
                        "url": item.get("url"),
                    }
                )
    coverage = {
        "archive_file_count": len(archive_files),
        "archive_date_min": min((item["date"] for item in archive_files), default=None),
        "archive_date_max": max((item["date"] for item in archive_files), default=None),
        "archive_files": archive_files,
        "positive_news_tickers": len(by_ticker),
        "positive_news_items": sum(len(items) for items in by_ticker.values()),
    }
    return by_ticker, coverage


def allowed_news_dates(dates: list[str], idx: int) -> set[str]:
    start = max(0, idx - MAX_NEWS_LOOKBACK_TRADING_DAYS)
    return set(dates[start : idx + 1])


def candidate_rows(
    snapshot: dict[str, list[dict]],
    ticker: str,
    dates: list[str],
    news_by_ticker: dict[str, list[dict]],
) -> list[dict]:
    rows = series(snapshot, ticker)
    if len(rows) < 30:
        return []
    idx_by_date = row_index(rows)
    spy_rows = series(snapshot, "SPY")
    spy_idx_by_date = row_index(spy_rows)
    ticker_news_by_date = defaultdict(list)
    for item in news_by_ticker.get(ticker, []):
        ticker_news_by_date[item["archive_date"]].append(item)

    candidates = []
    for date_pos, date in enumerate(dates):
        idx = idx_by_date.get(date)
        spy_idx = spy_idx_by_date.get(date)
        if idx is None or spy_idx is None or idx < 1 or spy_idx < 1:
            continue
        matched_news = [
            item
            for news_date in allowed_news_dates(dates, date_pos)
            for item in ticker_news_by_date.get(news_date, [])
        ]
        if not matched_news:
            continue

        cur = rows[idx]
        prev = rows[idx - 1]
        cur_open = value(cur, "Open")
        cur_close = value(cur, "Close")
        cur_volume = value(cur, "Volume")
        if cur_open is None or cur_close is None or cur_volume is None:
            continue
        dollar_volume = cur_close * cur_volume
        if dollar_volume < MIN_DOLLAR_VOLUME:
            continue

        event_return = close_return(rows, idx - 1, idx)
        spy_return = close_return(spy_rows, spy_idx - 1, spy_idx)
        if event_return is None or spy_return is None:
            continue
        rs_vs_spy = event_return - spy_return
        if event_return < MIN_EVENT_DAY_RETURN or rs_vs_spy <= MIN_EVENT_DAY_RS_VS_SPY:
            continue
        if cur_close <= cur_open:
            continue

        top_news = sorted(matched_news, key=lambda item: (-item["score"], str(item.get("published_at"))))[0]
        prev_close = value(prev, "Close")
        candidates.append(
            {
                "date": date,
                "ticker": ticker,
                "news_archive_dates": sorted({item["archive_date"] for item in matched_news}),
                "news_count": len(matched_news),
                "max_news_score": max(item["score"] for item in matched_news),
                "top_news_tier": top_news.get("tier"),
                "top_news_source": top_news.get("source"),
                "top_news_title": top_news.get("title"),
                "top_news_url": top_news.get("url"),
                "event_day_return": round(event_return, 6),
                "event_day_spy_return": round(spy_return, 6),
                "event_day_rs_vs_spy": round(rs_vs_spy, 6),
                "close_vs_open": round((cur_close / cur_open) - 1.0, 6) if cur_open else None,
                "close_vs_prev_close": round((cur_close / prev_close) - 1.0, 6) if prev_close else None,
                "dollar_volume": round(dollar_volume, 2),
                **{
                    f"fwd_{horizon}d": (
                        round(fwd, 6)
                        if isinstance((fwd := forward_return(rows, idx, horizon)), float)
                        else None
                    )
                    for horizon in FORWARD_DAYS
                },
            }
        )
    return candidates


def evaluate_window(label: str, cfg: dict, universe: list[str], news_by_ticker: dict[str, list[dict]]) -> dict:
    snapshot = load_snapshot(cfg["snapshot"])
    baseline = baseline_result(universe, cfg)
    entries_by_date = baseline_entries(baseline)
    dates = [date for date in trading_dates(snapshot) if cfg["start"] <= date <= cfg["end"]]

    candidates = []
    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker not in EXCLUDED_TICKERS:
            candidates.extend(candidate_rows(snapshot, ticker, dates, news_by_ticker))

    candidates.sort(key=lambda row: (row["date"], -row["max_news_score"], -row["event_day_rs_vs_spy"], row["ticker"]))
    for row in candidates:
        ab_entries = entries_by_date.get(row["date"], [])
        row["same_day_ab_entry_count"] = len(ab_entries)
        row["same_day_ab_overlap"] = bool(ab_entries)
        row["same_ticker_ab_overlap"] = any(trade.get("ticker") == row["ticker"] for trade in ab_entries)

    forward_summary = {}
    for horizon in FORWARD_DAYS:
        key = f"fwd_{horizon}d"
        forward_summary[key] = summarize([row[key] for row in candidates if isinstance(row.get(key), (int, float))])

    overlap = [row for row in candidates if row["same_day_ab_overlap"]]
    non_overlap = [row for row in candidates if not row["same_day_ab_overlap"]]
    news_dates_in_window = sorted(
        {
            item["archive_date"]
            for items in news_by_ticker.values()
            for item in items
            if cfg["start"] <= item["archive_date"] <= cfg["end"]
        }
    )
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "baseline_metrics": core_metrics(baseline),
        "clean_news_archive_dates_in_window": news_dates_in_window,
        "candidate_count": len(candidates),
        "candidate_unique_tickers": len({row["ticker"] for row in candidates}),
        "top_candidate_tickers": Counter(row["ticker"] for row in candidates).most_common(12),
        "forward_return_distribution": forward_summary,
        "scarce_slot_proxy": {
            "candidate_days": len({row["date"] for row in candidates}),
            "candidate_days_with_ab_entries": len({row["date"] for row in overlap}),
            "same_day_ab_overlap_count": len(overlap),
            "same_day_ab_overlap_rate": round(len(overlap) / len(candidates), 4) if candidates else None,
            "same_ticker_ab_overlap_count": sum(1 for row in candidates if row["same_ticker_ab_overlap"]),
            "avg_ab_entries_on_candidate_day": round(mean([row["same_day_ab_entry_count"] for row in candidates]), 4)
            if candidates
            else None,
            "fwd_10d_non_overlap": summarize(
                [row["fwd_10d"] for row in non_overlap if isinstance(row.get("fwd_10d"), (int, float))]
            ),
            "fwd_10d_overlap": summarize(
                [row["fwd_10d"] for row in overlap if isinstance(row.get("fwd_10d"), (int, float))]
            ),
        },
        "candidates": candidates,
        "sample_candidates": candidates[:40],
    }


def main() -> int:
    universe = get_universe()
    news_by_ticker, coverage = positive_clean_news_by_ticker()
    windows = [evaluate_window(label, cfg, universe, news_by_ticker) for label, cfg in WINDOWS.items()]

    aggregate_fwd10 = []
    aggregate_count = 0
    aggregate_overlap = 0
    positive_fwd10_windows = 0
    for window in windows:
        aggregate_count += window["candidate_count"]
        aggregate_overlap += window["scarce_slot_proxy"]["same_day_ab_overlap_count"]
        fwd10 = window["forward_return_distribution"]["fwd_10d"]
        if isinstance(fwd10.get("avg"), (int, float)) and fwd10["avg"] > 0:
            positive_fwd10_windows += 1
        aggregate_fwd10.extend(
            [row["fwd_10d"] for row in window["candidates"] if isinstance(row.get("fwd_10d"), (int, float))]
        )
        print(
            f"[{window['window']}] candidates={window['candidate_count']} "
            f"tickers={window['candidate_unique_tickers']} "
            f"news_days={len(window['clean_news_archive_dates_in_window'])} "
            f"overlap={window['scarce_slot_proxy']['same_day_ab_overlap_rate']} "
            f"fwd10_avg={fwd10['avg']} fwd10_wr={fwd10['win_rate']}"
        )

    multi_window_coverage = sum(1 for window in windows if window["candidate_count"] > 0)
    aggregate_summary = {
        "candidate_count": aggregate_count,
        "same_day_ab_overlap_count": aggregate_overlap,
        "same_day_ab_overlap_rate": round(aggregate_overlap / aggregate_count, 4) if aggregate_count else None,
        "aggregate_fwd10": summarize(aggregate_fwd10),
        "positive_fwd10_windows": positive_fwd10_windows,
        "windows_with_candidates": multi_window_coverage,
    }
    promotion_ready = (
        multi_window_coverage >= 2
        and positive_fwd10_windows >= 2
        and (aggregate_summary["aggregate_fwd10"].get("avg") or 0) > 0
    )
    decision = "observed_only" if promotion_ready else "rejected_shadow"
    reason = (
        "Shadow evidence has multi-window positive forward-return support."
        if promotion_ready
        else "Clean-news coverage still fails multi-window requirements or forward returns are not stable."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": decision,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_discovery",
        "hypothesis": (
            "Post-news continuation after archived clean positive news may be useful only if expanded archive "
            "coverage now produces multi-window candidates with positive forward returns and scarce-slot value."
        ),
        "single_causal_variable": "post-news continuation entry pattern",
        "prior_rejected_or_weak_evidence": {
            "exp-20260427-003": "58 late_strong candidates, no mid/old candidates, 10d avg -0.9682%, win rate 36.84%.",
            "exp-20260430-003_artifact": "Same mechanism remained single-window only and not promotion-ready.",
        },
        "mechanism_insight_check": {
            "do_not_repeat_conflict": True,
            "new_evidence_tested": "Whether clean_news archive coverage expanded after the prior run enough to cover fixed windows.",
            "result": reason,
        },
        "shadow_entry_definition": {
            "news_source": "data/clean_news_YYYYMMDD.json only",
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
        "coverage": coverage,
        "windows": windows,
        "aggregate_summary": aggregate_summary,
        "production_promotion": False,
        "production_promotion_reason": reason,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
        },
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"decision={decision} aggregate_fwd10={aggregate_summary['aggregate_fwd10']}")
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
