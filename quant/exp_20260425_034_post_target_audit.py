"""exp-20260425-034 post-target continuation audit.

Hypothesis:
    After the accepted Technology/Commodity target-width repairs and the 25%
    position cap, the next alpha may be winner lifecycle management. If target
    exits keep rising after exit, a continuation or re-entry rule may be more
    valuable than another residual haircut.

This script is audit-only. It does not change production strategy logic.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict, OrderedDict
from statistics import mean, median

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


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

HORIZONS = (5, 10, 20)
OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_034_post_target_audit.json")


def _scalar(value):
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def _load_window(universe: list[str], label: str, cfg: dict) -> tuple[dict, dict]:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    result = engine.run()
    ohlcv = engine._load_ohlcv_snapshot(os.path.join(REPO_ROOT, cfg["snapshot"]))
    return result, ohlcv


def _date_index_after(df: pd.DataFrame, date: str):
    ts = pd.Timestamp(date)
    dates = list(df.index)
    for idx, day in enumerate(dates):
        if day >= ts:
            return idx
    return None


def _return_between(df: pd.DataFrame, start_idx: int, horizon: int):
    target_idx = start_idx + horizon
    if target_idx >= len(df):
        return None
    start_close = _scalar(df.iloc[start_idx]["Close"])
    end_close = _scalar(df.iloc[target_idx]["Close"])
    if start_close <= 0:
        return None
    return round((end_close - start_close) / start_close, 6)


def _reentry_return(df: pd.DataFrame, start_idx: int, horizon: int):
    entry_idx = start_idx + 1
    target_idx = entry_idx + horizon
    if target_idx >= len(df):
        return None
    entry_open = _scalar(df.iloc[entry_idx]["Open"])
    end_close = _scalar(df.iloc[target_idx]["Close"])
    if entry_open <= 0:
        return None
    return round((end_close - entry_open) / entry_open, 6)


def _momentum(df: pd.DataFrame, idx: int, lookback: int = 20):
    if idx < lookback:
        return None
    now = _scalar(df.iloc[idx]["Close"])
    then = _scalar(df.iloc[idx - lookback]["Close"])
    if then <= 0:
        return None
    return round((now - then) / then, 6)


def _summarize(rows: list[dict]) -> dict:
    out = {"count": len(rows)}
    if not rows:
        return out
    for horizon in HORIZONS:
        values = [
            r[f"post_{horizon}d_return"]
            for r in rows
            if r.get(f"post_{horizon}d_return") is not None
        ]
        reentry_values = [
            r[f"reentry_{horizon}d_return"]
            for r in rows
            if r.get(f"reentry_{horizon}d_return") is not None
        ]
        out[f"post_{horizon}d_count"] = len(values)
        out[f"post_{horizon}d_avg"] = round(mean(values), 6) if values else None
        out[f"post_{horizon}d_median"] = round(median(values), 6) if values else None
        out[f"post_{horizon}d_win_rate"] = (
            round(sum(1 for v in values if v > 0) / len(values), 4)
            if values else None
        )
        out[f"reentry_{horizon}d_avg"] = (
            round(mean(reentry_values), 6) if reentry_values else None
        )
        out[f"reentry_{horizon}d_win_rate"] = (
            round(sum(1 for v in reentry_values if v > 0) / len(reentry_values), 4)
            if reentry_values else None
        )
    return out


def _group(rows: list[dict], *keys: str) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[" | ".join(str(row.get(k)) for k in keys)].append(row)
    return {
        key: _summarize(items)
        for key, items in sorted(grouped.items())
    }


def _classify_rs(row: dict) -> str:
    rel = row.get("rs20_vs_spy")
    if rel is None:
        return "rs_unknown"
    if rel >= 0.03:
        return "rs_strong"
    if rel >= 0:
        return "rs_neutral_positive"
    return "rs_weak"


def _audit_window(label: str, cfg: dict, universe: list[str]) -> dict:
    result, ohlcv = _load_window(universe, label, cfg)
    spy_df = ohlcv.get("SPY")
    qqq_df = ohlcv.get("QQQ")
    rows = []
    for trade in result.get("trades", []):
        if trade.get("exit_reason") != "target":
            continue
        ticker = trade.get("ticker")
        df = ohlcv.get(ticker)
        if df is None or df.empty:
            continue
        exit_idx = _date_index_after(df, trade.get("exit_date"))
        if exit_idx is None:
            continue
        spy_idx = _date_index_after(spy_df, trade.get("exit_date")) if spy_df is not None else None
        qqq_idx = _date_index_after(qqq_df, trade.get("exit_date")) if qqq_df is not None else None
        mom20 = _momentum(df, exit_idx)
        spy_mom20 = _momentum(spy_df, spy_idx) if spy_df is not None and spy_idx is not None else None
        qqq_mom20 = _momentum(qqq_df, qqq_idx) if qqq_df is not None and qqq_idx is not None else None
        row = {
            "window": label,
            "ticker": ticker,
            "strategy": trade.get("strategy"),
            "sector": trade.get("sector"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "exit_price": trade.get("exit_price"),
            "pnl_pct_net": trade.get("pnl_pct_net"),
            "target_mult_used": trade.get("target_mult_used"),
            "regime_exit_bucket": trade.get("regime_exit_bucket"),
            "regime_exit_score": trade.get("regime_exit_score"),
            "ticker_mom20_at_exit": mom20,
            "spy_mom20_at_exit": spy_mom20,
            "qqq_mom20_at_exit": qqq_mom20,
            "rs20_vs_spy": (
                round(mom20 - spy_mom20, 6)
                if mom20 is not None and spy_mom20 is not None else None
            ),
            "rs20_vs_qqq": (
                round(mom20 - qqq_mom20, 6)
                if mom20 is not None and qqq_mom20 is not None else None
            ),
        }
        row["rs_bucket"] = _classify_rs(row)
        for horizon in HORIZONS:
            row[f"post_{horizon}d_return"] = _return_between(df, exit_idx, horizon)
            row[f"reentry_{horizon}d_return"] = _reentry_return(df, exit_idx, horizon)
        rows.append(row)

    return {
        "window": label,
        "baseline": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe_daily": result.get("sharpe_daily"),
            "total_return_pct": (result.get("benchmarks") or {}).get(
                "strategy_total_return_pct"
            ),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "trade_count": result.get("total_trades"),
            "target_exit_count": len(rows),
        },
        "target_exit_rows": rows,
        "summary_all": _summarize(rows),
        "by_strategy_sector": _group(rows, "strategy", "sector"),
        "by_strategy_sector_rs": _group(rows, "strategy", "sector", "rs_bucket"),
        "by_sector_rs": _group(rows, "sector", "rs_bucket"),
    }


def main() -> int:
    universe = get_universe()
    windows = []
    all_rows = []
    for label, cfg in WINDOWS.items():
        item = _audit_window(label, cfg, universe)
        windows.append(item)
        all_rows.extend(item["target_exit_rows"])
        base = item["baseline"]
        print(
            f"[{label}] EV={base['expected_value_score']} "
            f"target_exits={base['target_exit_count']} "
            f"post10_avg={item['summary_all'].get('post_10d_avg')} "
            f"post10_win={item['summary_all'].get('post_10d_win_rate')}"
        )

    combined = {
        "summary_all": _summarize(all_rows),
        "by_strategy_sector": _group(all_rows, "strategy", "sector"),
        "by_strategy_sector_rs": _group(all_rows, "strategy", "sector", "rs_bucket"),
        "by_sector_rs": _group(all_rows, "sector", "rs_bucket"),
    }
    payload = {
        "experiment_id": "exp-20260425-034",
        "hypothesis": (
            "Target winners may contain continuation alpha after exit; if so, "
            "a future re-entry or hold-extension rule should be tested only "
            "where post-target continuation is stable across windows."
        ),
        "status": "audit_only",
        "windows": windows,
        "combined": combined,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
