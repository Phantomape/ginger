"""Shadow audit for exp-20260502-002.

This experiment does not change production behavior. It measures whether a
fresh multi-headline positive clean-news intensity event can identify useful,
non-overlapping candidates for future ranking or scarce-slot allocation work.
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


EXPERIMENT_ID = "exp-20260502-010"
STEM = "exp_20260502_010_fresh_multi_headline_positive_clean_news_intensity"
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
MIN_POSITIVE_ITEMS = 2
MAX_NEGATIVE_ITEMS = 0
MIN_DOLLAR_VOLUME = 25_000_000
NEWS_LOOKBACK_ARCHIVE_DAYS = 3
TICKER_COOLDOWN_TRADING_DAYS = 10

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
    r"approval|launch|partnership|contract|expands|expansion|accelerates)\b",
    re.IGNORECASE,
)
NEGATIVE_RE = re.compile(
    r"\b(downgrade|downgrades|downgraded|cuts|cut|trim|trims|trimmed|falls|fell|"
    r"drop|drops|dropped|plunge|plunges|plunged|crash|loser|lawsuit|probe|"
    r"investigation|bearish|warning|miss|misses|weak|slows|slowdown|concern)\b",
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


def news_counts_by_ticker_date() -> tuple[list[str], dict[tuple[str, str], dict]]:
    counts: dict[tuple[str, str], dict] = {}
    archive_dates = []
    data_dir = os.path.join(REPO_ROOT, "data")
    for name in sorted(os.listdir(data_dir)):
        if not (name.startswith("clean_news_") and name.endswith(".json")):
            continue
        payload = load_json(os.path.join(data_dir, name))
        if not isinstance(payload, list):
            continue
        archive_date = news_date_from_name(name)
        archive_dates.append(archive_date)
        for item in payload:
            if not isinstance(item, dict):
                continue
            text = f"{item.get('title') or ''} {item.get('summary') or ''}"
            positive_hits = len(POSITIVE_RE.findall(text))
            negative_hits = len(NEGATIVE_RE.findall(text))
            if positive_hits == 0 and negative_hits == 0:
                continue
            for ticker in [str(t).upper() for t in item.get("tickers") or []]:
                bucket = counts.setdefault(
                    (ticker, archive_date),
                    {
                        "ticker": ticker,
                        "date": archive_date,
                        "positive_items": 0,
                        "negative_items": 0,
                        "positive_hits": 0,
                        "negative_hits": 0,
                        "sample_titles": [],
                    },
                )
                if positive_hits > negative_hits:
                    bucket["positive_items"] += 1
                elif negative_hits > positive_hits:
                    bucket["negative_items"] += 1
                bucket["positive_hits"] += positive_hits
                bucket["negative_hits"] += negative_hits
                if len(bucket["sample_titles"]) < 3:
                    bucket["sample_titles"].append(str(item.get("title") or "")[:180])
    return sorted(set(archive_dates)), counts


def candidate_rows(snapshot: dict[str, list[dict]], cfg: dict, universe: list[str]) -> list[dict]:
    ordered_dates = trading_dates(snapshot)
    dates = set(ordered_dates)
    universe_set = set(universe)
    candidates = []
    archive_dates, counts = news_counts_by_ticker_date()
    last_signal_idx_by_ticker: dict[str, int] = {}
    for event_idx, event_date in enumerate(ordered_dates):
        if event_date < cfg["start"] or event_date > cfg["end"]:
            continue
        fresh_archives = [d for d in archive_dates if d <= event_date][-NEWS_LOOKBACK_ARCHIVE_DAYS:]
        if not fresh_archives:
            continue
        for ticker in sorted(universe_set - EXCLUDED_TICKERS):
            last_idx = last_signal_idx_by_ticker.get(ticker)
            if last_idx is not None and event_idx - last_idx < TICKER_COOLDOWN_TRADING_DAYS:
                continue
            merged = {
                "positive_items": 0,
                "negative_items": 0,
                "positive_hits": 0,
                "negative_hits": 0,
                "sample_titles": [],
                "archive_dates": [],
            }
            for archive_date in fresh_archives:
                info = counts.get((ticker, archive_date))
                if not info:
                    continue
                merged["positive_items"] += info["positive_items"]
                merged["negative_items"] += info["negative_items"]
                merged["positive_hits"] += info["positive_hits"]
                merged["negative_hits"] += info["negative_hits"]
                merged["archive_dates"].append(archive_date)
                for title in info["sample_titles"]:
                    if len(merged["sample_titles"]) < 3:
                        merged["sample_titles"].append(title)
            if merged["positive_items"] < MIN_POSITIVE_ITEMS or merged["negative_items"] > MAX_NEGATIVE_ITEMS:
                continue
            rows = series(snapshot, ticker)
            idx = row_index(rows).get(event_date)
            if idx is None:
                continue
            current = rows[idx]
            close = value(current, "Close")
            volume = value(current, "Volume")
            if not close or not volume or close * volume < MIN_DOLLAR_VOLUME:
                continue
            forward = {}
            for days in FORWARD_DAYS:
                ret = close_return(rows, idx, idx + days)
                forward[f"fwd_{days}d"] = ret
            last_signal_idx_by_ticker[ticker] = event_idx
            candidates.append(
                {
                    "ticker": ticker,
                    "date": event_date,
                    "positive_items": merged["positive_items"],
                    "negative_items": merged["negative_items"],
                    "positive_hits": merged["positive_hits"],
                    "negative_hits": merged["negative_hits"],
                    "archive_dates": merged["archive_dates"],
                    "dollar_volume": round(close * volume, 2),
                    "close": close,
                    "forward_returns": forward,
                    "sample_titles": merged["sample_titles"],
                }
            )
    return sorted(candidates, key=lambda row: (row["date"], -row["positive_items"], row["ticker"]))


def scarce_slot_proxy(candidates: list[dict], baseline_by_date: dict[str, list[dict]]) -> dict:
    comparisons = []
    for candidate in candidates:
        same_day = baseline_by_date.get(candidate["date"], [])
        if not same_day:
            continue
        fwd_10d = candidate["forward_returns"].get("fwd_10d")
        if fwd_10d is None:
            continue
        worst_trade = min(same_day, key=lambda t: float(t.get("pnl_pct_net") or 0.0))
        worst_pnl_pct = float(worst_trade.get("pnl_pct_net") or 0.0)
        comparisons.append(
            {
                "date": candidate["date"],
                "candidate": candidate["ticker"],
                "candidate_fwd_10d": fwd_10d,
                "overlap_trade_same_ticker": candidate["ticker"] == worst_trade.get("ticker"),
                "worst_same_day_trade": {
                    "ticker": worst_trade.get("ticker"),
                    "strategy": worst_trade.get("strategy"),
                    "pnl_pct_net": worst_pnl_pct,
                    "pnl": worst_trade.get("pnl"),
                },
                "candidate_minus_worst_trade_pct": fwd_10d - worst_pnl_pct,
            }
        )
    return {
        "comparison_count": len(comparisons),
        "candidate_minus_worst_trade_pct": summarize(
            [row["candidate_minus_worst_trade_pct"] for row in comparisons]
        ),
        "positive_replacement_rate": (
            round(sum(1 for row in comparisons if row["candidate_minus_worst_trade_pct"] > 0) / len(comparisons), 4)
            if comparisons
            else None
        ),
        "examples": comparisons[:20],
    }


def evaluate_window(name: str, cfg: dict, universe: list[str]) -> dict:
    snapshot = load_snapshot(cfg["snapshot"])
    baseline = run_baseline(universe, cfg)
    by_date = baseline_entries(baseline)
    candidates = candidate_rows(snapshot, cfg, universe)
    baseline_pairs = {(trade.get("ticker"), str(trade.get("entry_date"))[:10]) for trades in by_date.values() for trade in trades}
    candidate_pairs = {(row["ticker"], row["date"]) for row in candidates}
    overlap_pairs = candidate_pairs & baseline_pairs
    by_forward = {
        f"fwd_{days}d": summarize(
            [
                row["forward_returns"][f"fwd_{days}d"]
                for row in candidates
                if row["forward_returns"].get(f"fwd_{days}d") is not None
            ]
        )
        for days in FORWARD_DAYS
    }
    return {
        "window": name,
        "range": {"start": cfg["start"], "end": cfg["end"]},
        "baseline": metric_snapshot(baseline),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_tickers": len({row["ticker"] for row in candidates}),
        "overlap_with_existing_ab_entry_count": len(overlap_pairs),
        "overlap_with_existing_ab_entry_rate": round(len(overlap_pairs) / len(candidates), 4) if candidates else None,
        "forward_return_distribution": by_forward,
        "scarce_slot_proxy": scarce_slot_proxy(candidates, by_date),
        "top_candidates": candidates[:25],
    }


def main() -> None:
    universe = get_universe()
    results = OrderedDict()
    for name, cfg in WINDOWS.items():
        results[name] = evaluate_window(name, cfg, universe)

    aggregate_candidates = sum(row["candidate_count"] for row in results.values())
    aggregate_overlap = sum(row["overlap_with_existing_ab_entry_count"] for row in results.values())
    output = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "A fresh multi-headline positive clean-news intensity shadow mechanism can provide "
            "non-overlapping high-quality candidates without degrading expected value."
        ),
        "change_type": "new_strategy_shadow",
        "single_causal_variable": "fresh multi-headline positive clean-news intensity",
        "parameters": {
            "min_positive_items_same_clean_news_archive_day": MIN_POSITIVE_ITEMS,
            "max_negative_items_in_fresh_archive_window": MAX_NEGATIVE_ITEMS,
            "news_lookback_archive_days": NEWS_LOOKBACK_ARCHIVE_DAYS,
            "ticker_cooldown_trading_days": TICKER_COOLDOWN_TRADING_DAYS,
            "min_dollar_volume": MIN_DOLLAR_VOLUME,
            "forward_days": FORWARD_DAYS,
            "excluded_tickers": sorted(EXCLUDED_TICKERS),
            "baseline_config": BASE_CONFIG,
        },
        "history_guardrails": {
            "not_raw_ai_infra_pool": True,
            "not_spy_or_sector_leader_gate": True,
            "not_ohlcv_only_entry": True,
            "not_earnings_single_field_repair": True,
            "relation_to_prior_post_news": (
                "This is a stricter news-intensity audit requiring multiple positive clean-news items "
                "on the archive date and measuring it as a ranking/source-quality feature, not a raw "
                "post-news continuation entry."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
        "windows": results,
        "aggregate": {
            "candidate_count": aggregate_candidates,
            "overlap_with_existing_ab_entry_count": aggregate_overlap,
            "overlap_with_existing_ab_entry_rate": (
                round(aggregate_overlap / aggregate_candidates, 4) if aggregate_candidates else None
            ),
            "decision": "observed_only",
            "production_ready": False,
            "production_readiness_reason": (
                "Shadow/default-off audit only. It does not run a strategy-changing BacktestEngine replay "
                "or pass Gate 4, and historical clean-news coverage is sparse outside the late window."
            ),
        },
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(json.dumps(output["aggregate"], indent=2))
    print(OUT_JSON)


if __name__ == "__main__":
    main()
