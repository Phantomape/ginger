"""Experiment exp-20260429-030: sector state meta-allocation audit.

Read the canonical three fixed-window snapshots, run the real backtester,
annotate executed trades with entry-day sector breadth/dispersion features,
and write an observed-only experiment artifact. This script does not change
strategy behavior.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260429-030"
WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / accepted-stack dominant tape",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull after accepted allocation stack",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak older tape with the weakest win rate",
    },
}
BASELINE_METRICS = {
    "late_strong": {
        "expected_value_score": 2.3317,
        "sharpe_daily": 4.28,
        "total_pnl": 54479.38,
        "max_drawdown_pct": 0.0401,
        "win_rate": 0.7895,
        "trade_count": 19,
        "survival_rate": 0.8431,
    },
    "mid_weak": {
        "expected_value_score": 0.9672,
        "sharpe_daily": 2.53,
        "total_pnl": 38232.59,
        "max_drawdown_pct": 0.0616,
        "win_rate": 0.5238,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.2285,
        "sharpe_daily": 1.27,
        "total_pnl": 17991.28,
        "max_drawdown_pct": 0.0595,
        "win_rate": 0.4091,
        "trade_count": 22,
        "survival_rate": 0.9167,
    },
}


def load_universe() -> list[str]:
    try:
        from data_layer import get_universe

        return list(get_universe())
    except Exception:
        from filter import WATCHLIST

        return list(WATCHLIST)


def load_snapshot(path: Path) -> dict[str, pd.DataFrame]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    frames: dict[str, pd.DataFrame] = {}
    for ticker, rows in payload.get("ohlcv", {}).items():
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").set_index("Date")
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        frames[ticker.upper()] = df
    return frames


def last_row_on_or_before(df: pd.DataFrame, date: pd.Timestamp):
    subset = df.loc[df.index <= date]
    if subset.empty:
        return None
    return subset.iloc[-1], subset


def ticker_state(frames: dict[str, pd.DataFrame], ticker: str, date: pd.Timestamp):
    df = frames.get(ticker.upper())
    if df is None:
        return None
    found = last_row_on_or_before(df, date)
    if found is None:
        return None
    row, hist = found
    close = float(row.get("Close", float("nan")))
    if not math.isfinite(close):
        return None
    ret20 = None
    if len(hist) >= 21:
        prior = float(hist["Close"].iloc[-21])
        if prior:
            ret20 = close / prior - 1.0
    sma50 = float(hist["Close"].tail(50).mean()) if len(hist) >= 50 else None
    sma200 = float(hist["Close"].tail(200).mean()) if len(hist) >= 200 else None
    return {
        "close": close,
        "ret20": ret20,
        "above_sma50": bool(sma50 is not None and close > sma50),
        "above_sma200": bool(sma200 is not None and close > sma200),
        "has_sma50": sma50 is not None,
        "has_sma200": sma200 is not None,
    }


def sector_state(frames: dict[str, pd.DataFrame], sector: str, date: pd.Timestamp):
    states = []
    for ticker, mapped_sector in SECTOR_MAP.items():
        if mapped_sector != sector:
            continue
        state = ticker_state(frames, ticker, date)
        if state is not None:
            states.append(state)
    if not states:
        return {
            "sector_member_count": 0,
            "sector_breadth_50": None,
            "sector_breadth_200": None,
            "sector_avg_ret20": None,
            "sector_dispersion_20": None,
        }
    ret20_values = [s["ret20"] for s in states if s["ret20"] is not None]
    breadth50_base = [s for s in states if s["has_sma50"]]
    breadth200_base = [s for s in states if s["has_sma200"]]
    return {
        "sector_member_count": len(states),
        "sector_breadth_50": (
            sum(1 for s in breadth50_base if s["above_sma50"]) / len(breadth50_base)
            if breadth50_base
            else None
        ),
        "sector_breadth_200": (
            sum(1 for s in breadth200_base if s["above_sma200"]) / len(breadth200_base)
            if breadth200_base
            else None
        ),
        "sector_avg_ret20": (
            sum(ret20_values) / len(ret20_values) if ret20_values else None
        ),
        "sector_dispersion_20": (
            float(pd.Series(ret20_values).std(ddof=0)) if len(ret20_values) >= 2 else None
        ),
    }


def bucket_breadth(value):
    if value is None:
        return "unknown"
    if value < 0.5:
        return "breadth_lt_50"
    if value < 0.75:
        return "breadth_50_75"
    return "breadth_gte_75"


def bucket_ret20(value):
    if value is None:
        return "unknown"
    if value < 0:
        return "ret20_negative"
    if value < 0.05:
        return "ret20_0_5"
    return "ret20_gte_5"


def bucket_dispersion(value):
    if value is None:
        return "unknown"
    if value < 0.05:
        return "disp_lt_5"
    if value < 0.10:
        return "disp_5_10"
    return "disp_gte_10"


def bucket_relative(value):
    if value is None:
        return "unknown"
    if value < -0.03:
        return "sector_laggard"
    if value > 0.03:
        return "sector_leader"
    return "sector_inline"


def summarize(items):
    pnl = round(sum(float(t["pnl"]) for t in items), 2)
    n = len(items)
    wins = sum(1 for t in items if float(t["pnl"]) > 0)
    windows = sorted({t["window"] for t in items})
    return {
        "trades": n,
        "wins": wins,
        "win_rate": round(wins / n, 4) if n else 0,
        "pnl": pnl,
        "avg_pnl": round(pnl / n, 2) if n else 0,
        "windows": windows,
    }


def group_by(trades, key_fn):
    groups = defaultdict(list)
    for trade in trades:
        groups[key_fn(trade)].append(trade)
    return {
        str(key): summarize(items)
        for key, items in sorted(
            groups.items(), key=lambda kv: (-len(kv[1]), str(kv[0]))
        )
    }


def metrics(result):
    return {
        "expected_value_score": round(compute_expected_value_score(result), 4),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
    }


def annotate_trade(trade, window, frames):
    entry_date = pd.Timestamp(trade["entry_date"])
    sector = trade.get("sector", "Unknown")
    t_state = ticker_state(frames, trade["ticker"], entry_date) or {}
    s_state = sector_state(frames, sector, entry_date)
    ticker_ret20 = t_state.get("ret20")
    sector_avg = s_state.get("sector_avg_ret20")
    rel20 = (
        ticker_ret20 - sector_avg
        if ticker_ret20 is not None and sector_avg is not None
        else None
    )
    annotated = dict(trade)
    annotated.update(
        {
            "window": window,
            "ticker_ret20": ticker_ret20,
            "sector_ret20_relative": rel20,
            **s_state,
        }
    )
    annotated["state_buckets"] = {
        "sector_breadth_50": bucket_breadth(s_state["sector_breadth_50"]),
        "sector_breadth_200": bucket_breadth(s_state["sector_breadth_200"]),
        "sector_ret20": bucket_ret20(s_state["sector_avg_ret20"]),
        "sector_dispersion_20": bucket_dispersion(s_state["sector_dispersion_20"]),
        "ticker_vs_sector_ret20": bucket_relative(rel20),
    }
    return annotated


def candidate_notes(all_trades):
    notes = []
    for name, groups in {
        "strategy_sector_breadth200": group_by(
            all_trades,
            lambda t: (
                t.get("strategy"),
                t.get("sector"),
                t["state_buckets"]["sector_breadth_200"],
            ),
        ),
        "sector_breadth200_ret20": group_by(
            all_trades,
            lambda t: (
                t.get("sector"),
                t["state_buckets"]["sector_breadth_200"],
                t["state_buckets"]["sector_ret20"],
            ),
        ),
        "strategy_sector_relative": group_by(
            all_trades,
            lambda t: (
                t.get("strategy"),
                t.get("sector"),
                t["state_buckets"]["ticker_vs_sector_ret20"],
            ),
        ),
    }.items():
        stable = [
            {"group": key, **val}
            for key, val in groups.items()
            if val["trades"] >= 4 and len(val["windows"]) >= 2
        ]
        stable = sorted(stable, key=lambda x: x["pnl"], reverse=True)
        notes.append(
            {
                "view": name,
                "top_stable_positive": stable[:5],
                "bottom_stable_negative": sorted(stable, key=lambda x: x["pnl"])[:5],
            }
        )
    return notes


def main():
    universe = load_universe()
    all_annotated = []
    run_metrics = {}
    snapshot_metadata = {}

    for window, cfg in WINDOWS.items():
        snapshot_path = ROOT / cfg["snapshot"]
        frames = load_snapshot(snapshot_path)
        snapshot_metadata[window] = {
            "snapshot": cfg["snapshot"],
            "tickers": len(frames),
        }
        engine = BacktestEngine(
            universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(snapshot_path),
        )
        result = engine.run()
        run_metrics[window] = metrics(result)
        for trade in result.get("trades", []):
            all_annotated.append(annotate_trade(trade, window, frames))

    analysis = {
        "by_breadth_200": group_by(
            all_annotated, lambda t: t["state_buckets"]["sector_breadth_200"]
        ),
        "by_breadth_50": group_by(
            all_annotated, lambda t: t["state_buckets"]["sector_breadth_50"]
        ),
        "by_sector_ret20": group_by(
            all_annotated, lambda t: t["state_buckets"]["sector_ret20"]
        ),
        "by_sector_dispersion_20": group_by(
            all_annotated, lambda t: t["state_buckets"]["sector_dispersion_20"]
        ),
        "by_ticker_vs_sector_ret20": group_by(
            all_annotated, lambda t: t["state_buckets"]["ticker_vs_sector_ret20"]
        ),
        "by_strategy_sector_breadth_200": group_by(
            all_annotated,
            lambda t: (
                t.get("strategy"),
                t.get("sector"),
                t["state_buckets"]["sector_breadth_200"],
            ),
        ),
        "by_window_breadth_200": group_by(
            all_annotated,
            lambda t: (t.get("window"), t["state_buckets"]["sector_breadth_200"]),
        ),
        "candidate_state_notes": candidate_notes(all_annotated),
    }

    timestamp = datetime.now(timezone.utc).isoformat()
    record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only",
        "decision": "observed_only",
        "lane": "alpha_search",
        "change_type": "meta_allocation_audit",
        "hypothesis": (
            "Entry-day sector breadth, sector 20-day return, dispersion, and "
            "ticker-vs-sector relative strength may expose a robust allocation "
            "state that is better than another local multiplier tweak."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "why_not_llm_soft_ranking": (
            "LLM soft-ranking remains sample-limited for production-aligned "
            "replay, so this run tested a deterministic state map instead."
        ),
        "parameters": {
            "single_causal_variable": (
                "analysis-only sector state attribution; no executable policy changed"
            ),
            "state_features": [
                "sector_breadth_50",
                "sector_breadth_200",
                "sector_avg_ret20",
                "sector_dispersion_20",
                "ticker_ret20_minus_sector_avg_ret20",
            ],
            "locked_variables": [
                "signal generation",
                "entry filters",
                "candidate ranking",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "all exits",
                "gap cancels",
                "add-ons",
                "LLM/news replay",
                "earnings strategy",
                "all sizing multipliers",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "market_regime_summary": {
            name: cfg["regime"] for name, cfg in WINDOWS.items()
        },
        "before_metrics": BASELINE_METRICS,
        "after_metrics": BASELINE_METRICS,
        "run_metrics_observed": run_metrics,
        "expected_value_score_delta": {
            "late_strong": 0.0,
            "mid_weak": 0.0,
            "old_thin": 0.0,
            "aggregate": 0.0,
        },
        "analysis": analysis,
        "decision_reason": (
            "Observed only. The audit creates a reusable state map but does not "
            "promote a rule because no production-shared policy was tested."
        ),
        "next_retry_requires": [
            "A promoted sector-state rule must be implemented in shared production/backtest policy.",
            "Require at least two windows and material Gate 4 improvement before adding a state gate.",
            "Do not convert tiny one-sector pockets into filters without forward evidence.",
        ],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains data-limited; this alpha search "
                "deliberately used OHLCV-derived state features."
            ),
        },
        "snapshot_metadata": snapshot_metadata,
        "related_files": [
            f"data/experiments/{EXPERIMENT_ID}/sector_state_alpha_audit.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
        ],
    }

    artifact_dir = ROOT / "data" / "experiments" / EXPERIMENT_ID
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "sector_state_alpha_audit.json"
    log_path = ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    for path in [log_path.parent, ticket_path.parent]:
        path.mkdir(parents=True, exist_ok=True)

    artifact_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    log_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "title": "Sector state meta-allocation audit",
        "summary": (
            "OHLCV sector breadth/dispersion map written; no production rule promoted."
        ),
        "next_action": (
            "Use stable multi-window state buckets as candidates for a future shared-policy test."
        ),
        "related_files": record["related_files"],
    }
    ticket_path.write_text(json.dumps(ticket, indent=2), encoding="utf-8")

    jsonl_path = ROOT / "docs" / "experiment_log.jsonl"
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "trades": len(all_annotated),
        "artifact": str(artifact_path),
        "run_metrics": run_metrics,
        "top_breadth_200": analysis["by_breadth_200"],
    }, indent=2))


if __name__ == "__main__":
    main()
