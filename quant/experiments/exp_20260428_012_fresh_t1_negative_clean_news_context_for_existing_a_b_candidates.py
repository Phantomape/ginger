"""exp-20260428-012: negative clean-news context for A/B candidates.

Observed-only alpha discovery runner. It audits whether fresh negative
clean-news context separates lower-quality existing trend/breakout candidates.
No production strategy code is changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-012"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / (
    "exp_20260428_012_fresh_t1_negative_clean_news_context_for_existing_a_b_candidates.json"
)

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

FORWARD_HORIZONS = [1, 5, 10, 20]
NEWS_LOOKBACK_CALENDAR_DAYS = 2
NEGATIVE_TERMS = {
    "cut", "cuts", "delay", "delayed", "downgrade", "downgraded", "drop",
    "drops", "fall", "falls", "fraud", "investigation", "lawsuit", "miss",
    "misses", "negative", "probe", "slump", "warning", "weak",
}
POSITIVE_TERMS = {
    "accelerate", "accelerates", "approval", "approved", "beat", "beats",
    "bullish", "buy", "contract", "growth", "outperform", "partnership",
    "positive", "profit", "profits", "raised", "raises", "record",
    "strong", "surge", "surges", "upgrade", "upgraded",
}


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
    }


def _date_from_filename(path: Path) -> date | None:
    raw = path.stem.rsplit("_", 1)[-1]
    if len(raw) != 8 or not raw.isdigit():
        return None
    return date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))


def _term_score(text: str, terms: set[str]) -> int:
    lower = text.lower()
    return sum(1 for term in terms if term in lower)


def _negative_score(item: dict) -> int:
    text = f"{item.get('title') or ''} {item.get('summary') or ''}"
    negative = _term_score(text, NEGATIVE_TERMS)
    positive = _term_score(text, POSITIVE_TERMS)
    if negative <= 0 or negative <= positive:
        return 0
    if str(item.get("tier") or "").upper() == "T1":
        negative += 1
    return negative


def _load_negative_news_index() -> tuple[dict[str, list[dict]], dict]:
    by_ticker: dict[str, list[dict]] = {}
    archive_dates = []
    total_items = 0
    negative_items = 0
    strict_t1_negative_items = 0
    tier_counts: Counter[str] = Counter()
    for path in sorted((REPO_ROOT / "data").glob("clean_trade_news_*.json")):
        archive_date = _date_from_filename(path)
        if archive_date is None:
            continue
        archive_dates.append(archive_date.isoformat())
        payload = _load_json(path)
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            total_items += 1
            tier = str(item.get("tier") or "NONE").upper()
            tier_counts[tier] += 1
            score = _negative_score(item)
            if score <= 0:
                continue
            negative_items += 1
            if tier == "T1":
                strict_t1_negative_items += 1
            for ticker in [str(t).upper() for t in item.get("tickers") or [] if t]:
                by_ticker.setdefault(ticker, []).append({
                    "archive_date": archive_date.isoformat(),
                    "title": item.get("title"),
                    "tier": item.get("tier"),
                    "negative_score": score,
                    "strict_t1_negative": tier == "T1",
                    "published_at": item.get("published_at"),
                    "url": item.get("url"),
                })
    return by_ticker, {
        "archive_file_count": len(archive_dates),
        "archive_date_min": min(archive_dates) if archive_dates else None,
        "archive_date_max": max(archive_dates) if archive_dates else None,
        "total_items": total_items,
        "tier_counts": dict(tier_counts),
        "negative_items": negative_items,
        "strict_t1_negative_items": strict_t1_negative_items,
        "negative_tickers": len(by_ticker),
    }


def _matching_news(ticker: str, asof: str, news_by_ticker: dict[str, list[dict]]) -> list[dict]:
    asof_date = date.fromisoformat(asof[:10])
    start_date = asof_date - timedelta(days=NEWS_LOOKBACK_CALENDAR_DAYS)
    matches = []
    for item in news_by_ticker.get(ticker.upper(), []):
        archive_date = date.fromisoformat(item["archive_date"])
        if start_date <= archive_date <= asof_date:
            matches.append(item)
    return matches


def _load_frames(snapshot: str) -> dict[str, pd.DataFrame]:
    payload = _load_json(REPO_ROOT / snapshot)
    frames = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        df["Date"] = pd.to_datetime(df["Date"])
        frames[ticker.upper()] = df.set_index("Date").sort_index()
    return frames


def _forward_returns(frames: dict[str, pd.DataFrame], ticker: str, asof: str) -> dict:
    df = frames.get(ticker.upper())
    if df is None or df.empty:
        return {f"fwd_{h}d": None for h in FORWARD_HORIZONS}
    asof_ts = pd.Timestamp(asof[:10])
    hist = df.loc[:asof_ts]
    if hist.empty:
        return {f"fwd_{h}d": None for h in FORWARD_HORIZONS}
    idx = df.index.get_loc(hist.index[-1])
    base = float(df["Close"].iloc[idx])
    out = {}
    for horizon in FORWARD_HORIZONS:
        end_idx = idx + horizon
        if end_idx >= len(df) or base <= 0:
            out[f"fwd_{horizon}d"] = None
        else:
            out[f"fwd_{horizon}d"] = round(float(df["Close"].iloc[end_idx]) / base - 1.0, 6)
    return out


def _safe_mean(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    return round(mean(clean), 6) if clean else None


def _safe_median(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    return round(median(clean), 6) if clean else None


def _summarize_rows(rows: list[dict]) -> dict:
    realized = [float(r.get("realized_pnl") or 0.0) for r in rows if r.get("has_realized_pnl")]
    out = {
        "count": len(rows),
        "unique_tickers": len({r["ticker"] for r in rows}),
        "by_strategy": dict(Counter(r.get("strategy") for r in rows)),
        "strict_t1_negative_count": sum(1 for r in rows if r.get("strict_t1_negative")),
        "realized_pnl_sum": round(sum(realized), 2),
        "realized_win_rate": round(sum(1 for v in realized if v > 0) / len(realized), 4)
        if realized else None,
    }
    for horizon in FORWARD_HORIZONS:
        key = f"fwd_{horizon}d"
        values = [r.get(key) for r in rows if r.get(key) is not None]
        out[key] = {
            "count": len(values),
            "avg": _safe_mean(values),
            "median": _safe_median(values),
            "win_rate": round(sum(1 for v in values if v > 0) / len(values), 4) if values else None,
        }
    return out


def _run_window(universe: list[str], cfg: dict, news_by_ticker: dict[str, list[dict]]) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])

    frames = _load_frames(cfg["snapshot"])
    rows = []
    for trade in result.get("trades") or []:
        if trade.get("strategy") not in {"trend_long", "breakout_long"}:
            continue
        ticker = str(trade["ticker"]).upper()
        entry_date = str(trade["entry_date"])[:10]
        matches = _matching_news(ticker, entry_date, news_by_ticker)
        rows.append({
            "candidate_type": "executed_ab_entry",
            "ticker": ticker,
            "strategy": trade.get("strategy"),
            "sector": trade.get("sector"),
            "entry_date": entry_date,
            "overlap_with_existing_ab": True,
            "negative_news_confirmed": bool(matches),
            "strict_t1_negative": any(m.get("strict_t1_negative") for m in matches),
            "news_match_count": len(matches),
            "news_titles": [m.get("title") for m in matches[:3]],
            "realized_pnl": trade.get("pnl"),
            "realized_pnl_pct_net": trade.get("pnl_pct_net"),
            "has_realized_pnl": True,
            **_forward_returns(frames, ticker, entry_date),
        })

    deferred_rows = []
    for event in (result.get("scarce_slot_attribution") or {}).get("deferred_events") or []:
        ticker = str(event["ticker"]).upper()
        event_date = str(event["date"])[:10]
        matches = _matching_news(ticker, event_date, news_by_ticker)
        deferred_rows.append({
            "candidate_type": "scarce_slot_deferred_breakout",
            "ticker": ticker,
            "strategy": event.get("strategy"),
            "sector": event.get("sector"),
            "entry_date": event_date,
            "overlap_with_existing_ab": False,
            "negative_news_confirmed": bool(matches),
            "strict_t1_negative": any(m.get("strict_t1_negative") for m in matches),
            "news_match_count": len(matches),
            "news_titles": [m.get("title") for m in matches[:3]],
            "trade_quality_score": event.get("trade_quality_score"),
            "available_slots": event.get("available_slots"),
            "has_realized_pnl": False,
            **_forward_returns(frames, ticker, event_date),
        })

    confirmed = [r for r in rows if r["negative_news_confirmed"]]
    unconfirmed = [r for r in rows if not r["negative_news_confirmed"]]
    strict_t1 = [r for r in rows if r["strict_t1_negative"]]
    deferred_confirmed = [r for r in deferred_rows if r["negative_news_confirmed"]]
    deferred_unconfirmed = [r for r in deferred_rows if not r["negative_news_confirmed"]]

    return {
        "baseline_metrics": _metrics(result),
        "coverage": {
            "ab_entry_count": len(rows),
            "ab_overlap_rate": 1.0 if rows else None,
            "negative_confirmed_ab_entry_count": len(confirmed),
            "negative_confirmed_ab_entry_rate": round(len(confirmed) / len(rows), 4) if rows else None,
            "strict_t1_negative_ab_entry_count": len(strict_t1),
            "scarce_slot_deferred_count": len(deferred_rows),
            "negative_confirmed_deferred_count": len(deferred_confirmed),
        },
        "executed_ab_entries": {
            "negative_confirmed": _summarize_rows(confirmed),
            "strict_t1_negative": _summarize_rows(strict_t1),
            "unconfirmed": _summarize_rows(unconfirmed),
            "all": _summarize_rows(rows),
        },
        "scarce_slot_deferred_breakouts": {
            "negative_confirmed": _summarize_rows(deferred_confirmed),
            "unconfirmed": _summarize_rows(deferred_unconfirmed),
            "all": _summarize_rows(deferred_rows),
        },
        "sample_rows": rows[:20],
        "sample_deferred_rows": deferred_rows[:20],
    }


def run_experiment() -> dict:
    news_by_ticker, news_coverage = _load_negative_news_index()
    universe = get_universe()
    windows = OrderedDict()
    for label, cfg in WINDOWS.items():
        windows[label] = {
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "state_note": cfg["state_note"],
            **_run_window(universe, cfg, news_by_ticker),
        }
        cov = windows[label]["coverage"]
        confirmed = windows[label]["executed_ab_entries"]["negative_confirmed"]
        unconfirmed = windows[label]["executed_ab_entries"]["unconfirmed"]
        print(
            f"[{label}] A/B entries={cov['ab_entry_count']} "
            f"negative_confirmed={cov['negative_confirmed_ab_entry_count']} "
            f"strict_t1={cov['strict_t1_negative_ab_entry_count']} "
            f"confirmed_10d={confirmed['fwd_10d']['avg']} "
            f"unconfirmed_10d={unconfirmed['fwd_10d']['avg']}"
        )

    result = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "Fresh T1-negative clean-news context may identify lower-quality "
            "existing A/B candidates for future event-aware ranking without creating a new entry sleeve."
        ),
        "single_causal_variable": "fresh T1-negative clean-news context for existing A/B candidates",
        "shadow_definition": {
            "candidate_source": "executed trend_long/breakout_long entries plus scarce-slot deferred breakout audit events",
            "news_source": "archived data/clean_trade_news_YYYYMMDD.json only",
            "fresh_window_calendar_days": NEWS_LOOKBACK_CALENDAR_DAYS,
            "negative_classifier": "keyword negative score > positive score; explicit T1 tier recorded separately; no LLM used",
            "production_code_changed": False,
        },
        "news_coverage": news_coverage,
        "windows": windows,
        "production_promotion": False,
        "production_promotion_reason": (
            "Observed-only event-ranking audit. Strict T1-negative candidate coverage was absent, "
            "and broader negative clean-news matches were too sparse for production promotion."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    return result


if __name__ == "__main__":
    run_experiment()
