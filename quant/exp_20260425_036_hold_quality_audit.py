"""exp-20260425-036 hold-quality decay audit.

Hypothesis:
    After recent winner-truncation and position-cap improvements, the next
    distinct alpha mechanism may be capital release from positions whose
    early hold quality decays. If a position is still weak after 3/5/10 trading
    days, it may be lower-EV to keep occupying risk budget.

This script is audit/screen-only. It replays current accepted-stack trades and
estimates early-exit effects at the trade level. It does not model freed-slot
reinvestment, so any positive result must be promoted through the real
backtester before production.
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
from fill_model import SLIPPAGE_BPS_TARGET, apply_slippage  # noqa: E402
from portfolio_engine import ROUND_TRIP_COST_PCT  # noqa: E402


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

CHECKPOINTS = (3, 5, 10)
OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_036_hold_quality_audit.json")


VARIANTS = OrderedDict([
    ("d5_negative_and_rs_lag2", {"day": 5, "max_unrealized": 0.0, "max_rs": -0.02}),
    ("d5_negative_and_rs_lag5", {"day": 5, "max_unrealized": 0.0, "max_rs": -0.05}),
    ("d5_loss_gt3", {"day": 5, "max_unrealized": -0.03, "max_rs": None}),
    ("d10_negative_and_rs_lag2", {"day": 10, "max_unrealized": 0.0, "max_rs": -0.02}),
    ("d10_loss_gt3", {"day": 10, "max_unrealized": -0.03, "max_rs": None}),
])


def _scalar(value):
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def _load_window(universe: list[str], cfg: dict):
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
    for idx, day in enumerate(df.index):
        if day >= ts:
            return idx
    return None


def _safe_close(df: pd.DataFrame, idx: int):
    if idx < 0 or idx >= len(df):
        return None
    return _scalar(df.iloc[idx]["Close"])


def _return(df: pd.DataFrame, start_idx: int, end_idx: int):
    a = _safe_close(df, start_idx)
    b = _safe_close(df, end_idx)
    if a is None or b is None or a <= 0:
        return None
    return round((b - a) / a, 6)


def _summarize(values: list[float]) -> dict:
    clean = [v for v in values if v is not None]
    if not clean:
        return {"count": 0, "avg": None, "median": None, "win_rate": None}
    return {
        "count": len(clean),
        "avg": round(mean(clean), 6),
        "median": round(median(clean), 6),
        "win_rate": round(sum(1 for v in clean if v > 0) / len(clean), 4),
    }


def _variant_triggers(checkpoints: dict, rule: dict) -> bool:
    cp = checkpoints.get(str(rule["day"]))
    if not cp:
        return False
    unrealized = cp.get("unrealized_pct")
    if unrealized is None or unrealized > rule["max_unrealized"]:
        return False
    max_rs = rule.get("max_rs")
    if max_rs is None:
        return True
    rs = cp.get("rs_vs_spy")
    return rs is not None and rs <= max_rs


def _early_exit_pnl(trade: dict, checkpoint: dict) -> float:
    exit_raw = checkpoint["close"]
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    shares = trade.get("shares") or 0
    pnl = (
        (exit_price - trade["entry_price"]) * shares
        - exit_price * ROUND_TRIP_COST_PCT * shares
    )
    return round(pnl, 2)


def _audit_trade(trade: dict, ohlcv: dict) -> dict | None:
    ticker = trade.get("ticker")
    df = ohlcv.get(ticker)
    spy = ohlcv.get("SPY")
    if df is None or spy is None:
        return None
    entry_idx = _date_index_after(df, trade.get("entry_date"))
    exit_idx = _date_index_after(df, trade.get("exit_date"))
    spy_entry_idx = _date_index_after(spy, trade.get("entry_date"))
    if entry_idx is None or exit_idx is None or spy_entry_idx is None:
        return None
    if exit_idx <= entry_idx:
        return None

    checkpoints = {}
    for day in CHECKPOINTS:
        idx = entry_idx + day
        spy_idx = spy_entry_idx + day
        if idx >= exit_idx or idx >= len(df) or spy_idx >= len(spy):
            continue
        close = _safe_close(df, idx)
        if close is None or trade["entry_price"] <= 0:
            continue
        unrealized = round((close - trade["entry_price"]) / trade["entry_price"], 6)
        ticker_close_ret = _return(df, entry_idx, idx)
        spy_ret = _return(spy, spy_entry_idx, spy_idx)
        future_to_exit = round((trade["exit_price"] - close) / close, 6) if close > 0 else None
        checkpoints[str(day)] = {
            "date": str(df.index[idx].date()),
            "close": round(close, 4),
            "unrealized_pct": unrealized,
            "ticker_close_return": ticker_close_ret,
            "spy_return": spy_ret,
            "rs_vs_spy": (
                round(ticker_close_ret - spy_ret, 6)
                if ticker_close_ret is not None and spy_ret is not None else None
            ),
            "future_to_actual_exit_return": future_to_exit,
        }

    if not checkpoints:
        return None

    return {
        "ticker": ticker,
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "entry_price": trade.get("entry_price"),
        "exit_price": trade.get("exit_price"),
        "shares": trade.get("shares"),
        "actual_pnl": trade.get("pnl"),
        "actual_pnl_pct_net": trade.get("pnl_pct_net"),
        "days_held_trading": exit_idx - entry_idx,
        "checkpoints": checkpoints,
    }


def _screen_variant(rows: list[dict], rule: dict, baseline_pnl: float) -> dict:
    adjusted_pnl = baseline_pnl
    touched = []
    day = str(rule["day"])
    for row in rows:
        if not _variant_triggers(row["checkpoints"], rule):
            continue
        early_pnl = _early_exit_pnl(row, row["checkpoints"][day])
        delta = early_pnl - row["actual_pnl"]
        adjusted_pnl += delta
        touched.append({
            "ticker": row["ticker"],
            "strategy": row["strategy"],
            "sector": row["sector"],
            "entry_date": row["entry_date"],
            "checkpoint_date": row["checkpoints"][day]["date"],
            "actual_exit_date": row["exit_date"],
            "actual_exit_reason": row["exit_reason"],
            "actual_pnl": row["actual_pnl"],
            "early_exit_pnl": early_pnl,
            "pnl_delta": round(delta, 2),
            "checkpoint": row["checkpoints"][day],
        })
    return {
        "triggered_trades": len(touched),
        "pnl_delta_usd": round(sum(t["pnl_delta"] for t in touched), 2),
        "approx_total_pnl_usd": round(adjusted_pnl, 2),
        "touched": touched,
        "note": (
            "Approximation only: frees capital but does not replay replacement "
            "entries or equity-curve Sharpe."
        ),
    }


def _group_decay(rows: list[dict], day: int) -> dict:
    groups = defaultdict(list)
    for row in rows:
        cp = row["checkpoints"].get(str(day))
        if not cp:
            continue
        if cp["unrealized_pct"] <= -0.03:
            bucket = "loss_gt3"
        elif cp["unrealized_pct"] <= 0 and cp.get("rs_vs_spy") is not None and cp["rs_vs_spy"] <= -0.02:
            bucket = "negative_and_rs_lag2"
        elif cp["unrealized_pct"] <= 0:
            bucket = "negative"
        else:
            bucket = "positive"
        key = f"{row['strategy']} | {row['sector']} | {bucket}"
        groups[key].append(cp.get("future_to_actual_exit_return"))
    return {k: _summarize(v) for k, v in sorted(groups.items())}


def _audit_window(label: str, cfg: dict, universe: list[str]) -> dict:
    result, ohlcv = _load_window(universe, cfg)
    rows = []
    for trade in result.get("trades", []):
        item = _audit_trade(trade, ohlcv)
        if item:
            rows.append(item)

    baseline_pnl = result.get("total_pnl") or 0.0
    variant_results = {
        name: _screen_variant(rows, rule, baseline_pnl)
        for name, rule in VARIANTS.items()
    }
    return {
        "window": label,
        "baseline": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe_daily": result.get("sharpe_daily"),
            "total_return_pct": (result.get("benchmarks") or {}).get(
                "strategy_total_return_pct"
            ),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "total_pnl": result.get("total_pnl"),
            "trade_count": result.get("total_trades"),
            "auditable_trade_count": len(rows),
        },
        "decay_groups": {
            f"day_{day}": _group_decay(rows, day)
            for day in CHECKPOINTS
        },
        "variants": variant_results,
        "rows": rows,
    }


def main() -> int:
    universe = get_universe()
    windows = []
    for label, cfg in WINDOWS.items():
        item = _audit_window(label, cfg, universe)
        windows.append(item)
        base = item["baseline"]
        best = sorted(
            item["variants"].items(),
            key=lambda kv: kv[1]["pnl_delta_usd"],
            reverse=True,
        )[0]
        print(
            f"[{label}] EV={base['expected_value_score']} "
            f"pnl={base['total_pnl']} auditable={base['auditable_trade_count']} "
            f"best={best[0]} delta={best[1]['pnl_delta_usd']} "
            f"triggers={best[1]['triggered_trades']}"
        )
    payload = {
        "experiment_id": "exp-20260425-036",
        "status": "audit_screen_only",
        "hypothesis": (
            "Early hold-quality decay may identify low-EV positions before the "
            "normal stop/target lifecycle completes."
        ),
        "variants": VARIANTS,
        "windows": windows,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
