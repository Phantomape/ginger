"""exp-20260426-009 entry follow-through audit.

Hypothesis:
    Recent accepted improvements mostly came from letting proven winners earn
    more, not from trimming weak starts. The next distinct alpha mechanism may
    be entry follow-through: if a position proves itself in the first 1-3
    trading days, it may deserve more capital via future ranking/add-on logic.

Audit/screen only. The add-on screen is a trade-level approximation and does
not model freed slots, portfolio heat, or full equity-curve effects.
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
from fill_model import apply_entry_fill  # noqa: E402
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

CHECKPOINTS = (1, 2, 3)
ADD_FRACTION = 0.25
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_009_entry_followthrough_audit.json",
)

ADDON_RULES = OrderedDict([
    ("d1_pos_rs_pos", {"day": 1, "min_unrealized": 0.0, "min_rs": 0.0}),
    ("d2_pos_rs_pos", {"day": 2, "min_unrealized": 0.0, "min_rs": 0.0}),
    ("d3_pos_rs_pos", {"day": 3, "min_unrealized": 0.0, "min_rs": 0.0}),
    ("d2_gt2_rs_pos", {"day": 2, "min_unrealized": 0.02, "min_rs": 0.0}),
    ("d3_gt2_rs_pos", {"day": 3, "min_unrealized": 0.02, "min_rs": 0.0}),
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


def _safe_price(df: pd.DataFrame, idx: int, column: str):
    if idx < 0 or idx >= len(df):
        return None
    return _scalar(df.iloc[idx][column])


def _return(df: pd.DataFrame, start_idx: int, end_idx: int):
    a = _safe_price(df, start_idx, "Close")
    b = _safe_price(df, end_idx, "Close")
    if a is None or b is None or a <= 0:
        return None
    return round((b - a) / a, 6)


def _summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"count": 0}
    pnls = [r["actual_pnl"] for r in rows if r.get("actual_pnl") is not None]
    pnl_pcts = [
        r["actual_pnl_pct_net"]
        for r in rows
        if r.get("actual_pnl_pct_net") is not None
    ]
    return {
        "count": len(rows),
        "avg_pnl": round(mean(pnls), 2) if pnls else None,
        "median_pnl": round(median(pnls), 2) if pnls else None,
        "avg_pnl_pct": round(mean(pnl_pcts), 6) if pnl_pcts else None,
        "win_rate": (
            round(sum(1 for r in rows if (r.get("actual_pnl") or 0) > 0) / len(rows), 4)
            if rows else None
        ),
        "target_rate": (
            round(sum(1 for r in rows if r.get("exit_reason") == "target") / len(rows), 4)
            if rows else None
        ),
        "stop_rate": (
            round(sum(1 for r in rows if r.get("exit_reason") in {"stop", "trailing_stop"}) / len(rows), 4)
            if rows else None
        ),
    }


def _bucket_checkpoint(cp: dict) -> str:
    unreal = cp.get("unrealized_pct")
    rs = cp.get("rs_vs_spy")
    if unreal is None:
        return "unknown"
    if unreal >= 0.02 and rs is not None and rs > 0:
        return "strong_gt2_rs_pos"
    if unreal > 0 and rs is not None and rs > 0:
        return "pos_rs_pos"
    if unreal > 0:
        return "pos_rs_lag_or_unknown"
    if unreal <= -0.02:
        return "weak_lt_minus2"
    return "flat_to_negative"


def _rule_match(cp: dict, rule: dict) -> bool:
    unreal = cp.get("unrealized_pct")
    rs = cp.get("rs_vs_spy")
    if unreal is None or unreal < rule["min_unrealized"]:
        return False
    if rs is None or rs < rule["min_rs"]:
        return False
    return True


def _addon_delta(trade: dict, df: pd.DataFrame, checkpoint_idx: int) -> dict | None:
    addon_idx = checkpoint_idx + 1
    exit_idx = _date_index_after(df, trade.get("exit_date"))
    if exit_idx is None or addon_idx >= exit_idx or addon_idx >= len(df):
        return None
    raw_open = _safe_price(df, addon_idx, "Open")
    if raw_open is None:
        return None
    addon_entry = apply_entry_fill(raw_open)
    addon_shares = int((trade.get("shares") or 0) * ADD_FRACTION)
    if addon_shares <= 0:
        return None
    exit_price = trade.get("exit_price")
    if exit_price is None:
        return None
    cost = exit_price * ROUND_TRIP_COST_PCT * addon_shares
    pnl = (exit_price - addon_entry) * addon_shares - cost
    return {
        "addon_date": str(df.index[addon_idx].date()),
        "addon_entry_price": round(addon_entry, 4),
        "addon_shares": addon_shares,
        "addon_pnl": round(pnl, 2),
    }


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
        close = _safe_price(df, idx, "Close")
        if close is None or (trade.get("entry_price") or 0) <= 0:
            continue
        ticker_ret = _return(df, entry_idx, idx)
        spy_ret = _return(spy, spy_entry_idx, spy_idx)
        cp = {
            "date": str(df.index[idx].date()),
            "close": round(close, 4),
            "unrealized_pct": round(
                (close - trade["entry_price"]) / trade["entry_price"],
                6,
            ),
            "ticker_close_return": ticker_ret,
            "spy_return": spy_ret,
            "rs_vs_spy": (
                round(ticker_ret - spy_ret, 6)
                if ticker_ret is not None and spy_ret is not None else None
            ),
        }
        cp["bucket"] = _bucket_checkpoint(cp)
        checkpoints[str(day)] = cp

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


def _group_by_checkpoint(rows: list[dict]) -> dict:
    out = {}
    for day in CHECKPOINTS:
        groups = defaultdict(list)
        for row in rows:
            cp = row["checkpoints"].get(str(day))
            if not cp:
                continue
            groups[cp["bucket"]].append(row)
            groups[f"{row['strategy']} | {cp['bucket']}"].append(row)
            groups[f"{row['strategy']} | {row['sector']} | {cp['bucket']}"].append(row)
        out[f"day_{day}"] = {
            key: _summarize(items)
            for key, items in sorted(groups.items())
            if len(items) >= 1
        }
    return out


def _screen_addons(rows: list[dict], ohlcv: dict) -> dict:
    out = {}
    for name, rule in ADDON_RULES.items():
        day = str(rule["day"])
        touched = []
        for row in rows:
            cp = row["checkpoints"].get(day)
            if not cp or not _rule_match(cp, rule):
                continue
            df = ohlcv.get(row["ticker"])
            if df is None:
                continue
            checkpoint_idx = _date_index_after(df, cp["date"])
            if checkpoint_idx is None:
                continue
            addon = _addon_delta(row, df, checkpoint_idx)
            if not addon:
                continue
            touched.append({
                "ticker": row["ticker"],
                "strategy": row["strategy"],
                "sector": row["sector"],
                "entry_date": row["entry_date"],
                "checkpoint_date": cp["date"],
                "actual_exit_date": row["exit_date"],
                "actual_exit_reason": row["exit_reason"],
                "actual_pnl": row["actual_pnl"],
                "checkpoint": cp,
                **addon,
            })
        out[name] = {
            "triggered_trades": len(touched),
            "addon_pnl_usd": round(sum(t["addon_pnl"] for t in touched), 2),
            "touched": touched,
            "note": (
                f"Approximation: add {ADD_FRACTION:.0%} of original shares at "
                "next open after checkpoint, exit with original trade."
            ),
        }
    return out


def _audit_window(label: str, cfg: dict, universe: list[str]) -> dict:
    result, ohlcv = _load_window(universe, cfg)
    rows = []
    for trade in result.get("trades", []):
        item = _audit_trade(trade, ohlcv)
        if item:
            rows.append(item)
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
        "checkpoint_groups": _group_by_checkpoint(rows),
        "addon_screens": _screen_addons(rows, ohlcv),
        "rows": rows,
    }


def main() -> int:
    universe = get_universe()
    windows = []
    for label, cfg in WINDOWS.items():
        item = _audit_window(label, cfg, universe)
        windows.append(item)
        best = sorted(
            item["addon_screens"].items(),
            key=lambda kv: kv[1]["addon_pnl_usd"],
            reverse=True,
        )[0]
        print(
            f"[{label}] EV={item['baseline']['expected_value_score']} "
            f"auditable={item['baseline']['auditable_trade_count']} "
            f"best={best[0]} addon_pnl={best[1]['addon_pnl_usd']} "
            f"triggers={best[1]['triggered_trades']}"
        )

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "experiment_id": "exp-20260426-009",
            "status": "audit_screen_only",
            "hypothesis": (
                "Early entry follow-through may predict final winners and could "
                "support future ranking/add-on logic."
            ),
            "add_fraction": ADD_FRACTION,
            "addon_rules": ADDON_RULES,
            "windows": windows,
        }, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
