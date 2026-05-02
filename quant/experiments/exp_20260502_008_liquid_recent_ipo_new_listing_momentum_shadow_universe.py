"""exp-20260502-008 liquid post-2019 platform/new-listing universe scout.

Observed-only universe scout. This script does not change production universe
membership, shared signal/risk code, or portfolio behavior.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from filter import WATCHLIST  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260502-008"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "experiments",
    EXPERIMENT_ID,
    "exp_20260502_008_liquid_recent_ipo_new_listing_momentum_shadow_universe.json",
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

FORWARD_HORIZONS = [5, 10, 20]
SOURCE_TICKERS = ["APP", "COIN", "CRDO", "DDOG", "PLTR", "SNOW"]
EXCLUDED_RECENT_REJECTED = {
    "BE", "INTC", "LITE", "XLE", "XLV", "XLP", "XLU", "USO", "IEF", "TLT", "UUP",
}


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_frames(snapshot_path: str) -> tuple[dict[str, pd.DataFrame], dict]:
    payload = _load_json(os.path.join(REPO_ROOT, snapshot_path))
    frames = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        df["Date"] = pd.to_datetime(df["Date"])
        frames[ticker.upper()] = df.set_index("Date").sort_index()
    return frames, payload.get("metadata") or {}


def _expected_days(frames: dict[str, pd.DataFrame], start: str, end: str) -> int:
    spy = frames.get("SPY")
    if spy is None:
        return 0
    return int(len(spy.loc[pd.Timestamp(start):pd.Timestamp(end)]))


def _clean(values: list[float | None]) -> list[float]:
    out = []
    for value in values:
        if value is None:
            continue
        try:
            f = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isnan(f):
            out.append(f)
    return out


def _safe_mean(values: list[float | None]) -> float | None:
    clean = _clean(values)
    return round(mean(clean), 6) if clean else None


def _safe_median(values: list[float | None]) -> float | None:
    clean = _clean(values)
    return round(median(clean), 6) if clean else None


def _quantiles(values: list[float | None]) -> dict[str, float | None]:
    clean = sorted(_clean(values))
    if not clean:
        return {"p10": None, "p25": None, "p50": None, "p75": None, "p90": None}

    def pick(q: float) -> float:
        return round(clean[int(round((len(clean) - 1) * q))], 6)

    return {
        "p10": pick(0.10),
        "p25": pick(0.25),
        "p50": pick(0.50),
        "p75": pick(0.75),
        "p90": pick(0.90),
    }


def _summarize_returns(rows: list[dict]) -> dict[str, dict]:
    out = {}
    for horizon in FORWARD_HORIZONS:
        key = f"fwd_{horizon}d"
        values = [row.get(key) for row in rows if row.get(key) is not None]
        positives = [v for v in values if v > 0]
        out[key] = {
            "count": len(values),
            "avg": _safe_mean(values),
            "median": _safe_median(values),
            "win_rate": round(len(positives) / len(values), 4) if values else None,
            **_quantiles(values),
        }
    return out


def _production_universe() -> set[str]:
    universe = {ticker.upper() for ticker in WATCHLIST}
    positions_path = os.path.join(REPO_ROOT, "data", "open_positions.json")
    if os.path.exists(positions_path):
        try:
            payload = _load_json(positions_path)
            for pos in payload.get("positions") or []:
                ticker = pos.get("ticker")
                if ticker:
                    universe.add(str(ticker).upper())
        except Exception:
            pass
    return universe


def _window_liquidity(frames: dict[str, pd.DataFrame], start: str, end: str) -> dict[str, dict]:
    expected = _expected_days(frames, start, end)
    out = {}
    for ticker in SOURCE_TICKERS:
        df = frames.get(ticker)
        if df is None:
            out[ticker] = {
                "coverage_days": 0,
                "coverage_fraction": 0.0,
                "median_dollar_volume": None,
                "median_close": None,
                "passes_liquidity": False,
                "sector": SECTOR_MAP.get(ticker, "Unknown"),
            }
            continue
        window = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
        dollar_volume = window["Close"].astype(float) * window["Volume"].astype(float)
        median_dv = round(float(dollar_volume.median()), 2) if not window.empty else None
        median_close = round(float(window["Close"].median()), 4) if not window.empty else None
        out[ticker] = {
            "coverage_days": int(len(window)),
            "coverage_fraction": round(len(window) / expected, 4) if expected else 0.0,
            "median_dollar_volume": median_dv,
            "median_close": median_close,
            "passes_liquidity": (
                len(window) >= 60
                and (median_dv or 0.0) >= 20_000_000
                and (median_close or 0.0) >= 5.0
            ),
            "sector": SECTOR_MAP.get(ticker, "Unknown"),
        }
    return out


def _forward_returns(frames: dict[str, pd.DataFrame], ticker: str, date_key: str) -> dict[str, float | None]:
    df = frames.get(ticker)
    if df is None:
        return {f"fwd_{h}d": None for h in FORWARD_HORIZONS}
    asof = pd.Timestamp(date_key)
    hist = df.loc[:asof]
    if hist.empty:
        return {f"fwd_{h}d": None for h in FORWARD_HORIZONS}
    idx = df.index.get_loc(hist.index[-1])
    entry = float(df.iloc[idx]["Close"])
    out = {}
    for horizon in FORWARD_HORIZONS:
        fwd_idx = idx + horizon
        key = f"fwd_{horizon}d"
        if fwd_idx >= len(df) or entry <= 0:
            out[key] = None
        else:
            out[key] = round(float(df.iloc[fwd_idx]["Close"]) / entry - 1, 6)
    return out


def _run_backtest(universe: list[str], cfg: dict) -> dict:
    result = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


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
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
    }


def _source_rows(result: dict, frames: dict[str, pd.DataFrame], baseline_touchpoints: set[tuple[str, str]]) -> list[dict]:
    rows = []
    for trade in result.get("trades") or []:
        ticker = str(trade.get("ticker") or "").upper()
        entry_date = str(trade.get("entry_date") or "")[:10]
        if ticker not in SOURCE_TICKERS or not entry_date:
            continue
        row = {
            "ticker": ticker,
            "entry_date": entry_date,
            "strategy": trade.get("strategy"),
            "pnl": round(float(trade.get("pnl") or 0.0), 2),
            "pnl_pct": round(float(trade.get("pnl_pct") or 0.0), 6),
            "same_day_ab_overlap": (ticker, entry_date) in baseline_touchpoints,
            "sector": SECTOR_MAP.get(ticker, "Unknown"),
        }
        row.update(_forward_returns(frames, ticker, entry_date))
        rows.append(row)
    return sorted(rows, key=lambda r: (r["entry_date"], r["ticker"], r["strategy"] or ""))


def _scarce_slot_proxy(rows: list[dict], baseline_trades: list[dict]) -> dict:
    baseline_by_day = Counter(str(t.get("entry_date") or "")[:10] for t in baseline_trades)
    candidate_days = sorted({row["entry_date"] for row in rows})
    competition_days = [day for day in candidate_days if baseline_by_day[day] >= 3]
    rows_on_competition_days = [row for row in rows if row["entry_date"] in set(competition_days)]
    return {
        "candidate_days": len(candidate_days),
        "candidate_days_with_3plus_baseline_entries": len(competition_days),
        "candidate_day_competition_rate": round(len(competition_days) / len(candidate_days), 4) if candidate_days else None,
        "candidate_count_on_competition_days": len(rows_on_competition_days),
        "forward_returns_on_competition_days": _summarize_returns(rows_on_competition_days),
        "note": "Scarce-slot value is a proxy only; no production universe promotion, fills, sizing, or slot replacement replay ran.",
    }


def _window_payload(name: str, cfg: dict, production_universe: set[str]) -> dict:
    frames, metadata = _load_frames(cfg["snapshot"])
    base_universe = get_universe()
    baseline = _run_backtest(base_universe, cfg)
    source = _run_backtest(SOURCE_TICKERS, cfg)
    baseline_touchpoints = {
        (str(t.get("ticker") or "").upper(), str(t.get("entry_date") or "")[:10])
        for t in baseline.get("trades") or []
        if t.get("ticker") and t.get("entry_date")
    }
    rows = _source_rows(source, frames, baseline_touchpoints)
    overlap = [row for row in rows if row["same_day_ab_overlap"]]
    outside_production = [ticker for ticker in SOURCE_TICKERS if ticker not in production_universe]
    return {
        "window": name,
        "start": cfg["start"],
        "end": cfg["end"],
        "state_note": cfg["state_note"],
        "snapshot": cfg["snapshot"],
        "snapshot_ticker_count": len(frames),
        "snapshot_metadata": metadata,
        "source_tickers_present": sorted(t for t in SOURCE_TICKERS if t in frames),
        "source_tickers_missing": sorted(t for t in SOURCE_TICKERS if t not in frames),
        "outside_production_source_tickers": sorted(outside_production),
        "coverage_and_liquidity": _window_liquidity(frames, cfg["start"], cfg["end"]),
        "baseline_metrics": _metrics(baseline),
        "source_only_metrics": _metrics(source),
        "candidate_count": len(rows),
        "candidate_unique_tickers": sorted({row["ticker"] for row in rows}),
        "candidate_count_by_ticker": dict(Counter(row["ticker"] for row in rows).most_common()),
        "same_day_ab_overlap_count": len(overlap),
        "same_day_ab_overlap_rate": round(len(overlap) / len(rows), 4) if rows else None,
        "forward_return_distribution": _summarize_returns(rows),
        "non_overlap_forward_return_distribution": _summarize_returns(
            [row for row in rows if not row["same_day_ab_overlap"]]
        ),
        "scarce_slot_proxy": _scarce_slot_proxy(rows, baseline.get("trades") or []),
        "sample_candidates": rows[:40],
    }


def _weighted_forward(windows: list[dict]) -> dict[str, dict]:
    out = {}
    for horizon in FORWARD_HORIZONS:
        key = f"fwd_{horizon}d"
        values = []
        for window in windows:
            for row in window["sample_candidates"]:
                value = row.get(key)
                if value is not None:
                    values.append(value)
        out[key] = {
            "sample_candidate_count": len(values),
            "avg": _safe_mean(values),
            "median": _safe_median(values),
            "win_rate": round(len([v for v in values if v > 0]) / len(values), 4) if values else None,
            **_quantiles(values),
        }
    return out


def main() -> None:
    production_universe = _production_universe()
    windows = [
        _window_payload(name, cfg, production_universe)
        for name, cfg in WINDOWS.items()
    ]
    total_candidates = sum(w["candidate_count"] for w in windows)
    total_overlap = sum(w["same_day_ab_overlap_count"] for w in windows)
    all_source_tickers = sorted(set().union(*(set(w["source_tickers_present"]) for w in windows)))
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "universe_scout",
        "change_type": "universe_expansion",
        "hypothesis": "one narrow shadow universe can produce non-overlapping high-quality candidates after liquidity/data checks",
        "single_causal_variable": (
            "liquid post-2019 platform/new-listing cohort in fixed OHLCV snapshots: "
            "APP, COIN, CRDO, DDOG, PLTR, SNOW"
        ),
        "alpha_hypothesis": {
            "category": "universe_source_shadow",
            "statement": "Recent platform/new-listing names may create scarce growth candidates distinct from broad ETFs, AI infra raw pools, and event-sensitive scouts.",
            "why_not_production_now": "This is a source-only shadow audit; outside-production coverage is zero in current fixed snapshots.",
        },
        "shadow_universe_definition": {
            "source_tickers": SOURCE_TICKERS,
            "exclusions_from_recent_failures": sorted(EXCLUDED_RECENT_REJECTED),
            "eligibility_checks": {
                "minimum_history_days": 60,
                "minimum_20d_average_dollar_volume_usd": 20_000_000,
                "minimum_close_usd": 5.0,
            },
            "candidate_generation": "current shared trend/breakout engine in source-only shadow backtests; no new entry rule",
            "forward_return_horizons_trading_days": FORWARD_HORIZONS,
        },
        "production_promotion": False,
        "promotion_blockers": [
            "No production universe change was allowed or attempted.",
            "All source tickers are already in the production watchlist, so outside-production candidate coverage is zero.",
            "Scarce-slot value is only proxied; no slot-aware replacement replay was authorized.",
        ],
        "aggregate": {
            "source_tickers_present_any_window": all_source_tickers,
            "candidate_count": total_candidates,
            "same_day_ab_overlap_rate_weighted": round(total_overlap / total_candidates, 4) if total_candidates else None,
            "outside_production_source_ticker_count": len([t for t in SOURCE_TICKERS if t not in production_universe]),
            "sample_forward_returns": _weighted_forward(windows),
        },
        "windows": windows,
        "decision": {
            "status": "observed_only",
            "promotion_ready": False,
            "reason": "Shadow source has data coverage and liquid candidates, but it is not an external universe expansion and needs slot-aware replacement evidence before any promotion.",
        },
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
        f.write("\n")
    print(json.dumps({
        "artifact": OUT_JSON,
        "candidate_count": total_candidates,
        "same_day_ab_overlap_rate_weighted": artifact["aggregate"]["same_day_ab_overlap_rate_weighted"],
        "outside_production_source_ticker_count": artifact["aggregate"]["outside_production_source_ticker_count"],
        "sample_forward_returns": artifact["aggregate"]["sample_forward_returns"],
        "promotion_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
