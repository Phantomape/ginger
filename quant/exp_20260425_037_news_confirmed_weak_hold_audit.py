"""exp-20260425-037 news-confirmed weak-hold audit.

Hypothesis:
    Simple day-5/day-10 weak-hold exits were rejected because weak starts can
    become large winners. A stronger lifecycle signal may require both price
    weakness and fresh adverse information. This audit checks whether weak
    in-position states near archived T1-negative news would have improved exits.

Audit only. No production strategy logic is changed.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict
from datetime import timedelta

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_slippage  # noqa: E402
from news_replay import get_news_for_date  # noqa: E402
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

CHECKPOINTS = (5, 10)
NEWS_LOOKAROUND_DAYS = 3
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260425_037_news_confirmed_weak_hold_audit.json",
)


WEAK_RULES = OrderedDict([
    ("negative_and_rs_lag2", {"max_unrealized": 0.0, "max_rs": -0.02}),
    ("loss_gt3", {"max_unrealized": -0.03, "max_rs": None}),
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


def _news_window(checkpoint_date: str, ticker: str) -> dict:
    center = pd.Timestamp(checkpoint_date).date()
    covered = []
    missing = []
    t1_negative_dates = []
    all_t1_dates = []
    for offset in range(-NEWS_LOOKAROUND_DAYS, NEWS_LOOKAROUND_DAYS + 1):
        day = center + timedelta(days=offset)
        decision = get_news_for_date(day, os.path.join(REPO_ROOT, "data"))
        if decision["file_present"]:
            covered.append(decision["date_str"])
        else:
            missing.append(decision["date_str"])
        upper = ticker.upper()
        if upper in decision["all_t1_tickers"]:
            all_t1_dates.append(decision["date_str"])
        if upper in decision["t1_negative_tickers"]:
            t1_negative_dates.append(decision["date_str"])
    return {
        "covered_dates": covered,
        "missing_dates": missing,
        "coverage_fraction": round(len(covered) / (2 * NEWS_LOOKAROUND_DAYS + 1), 4),
        "all_t1_dates": all_t1_dates,
        "t1_negative_dates": t1_negative_dates,
        "has_t1_negative": bool(t1_negative_dates),
        "has_any_t1": bool(all_t1_dates),
    }


def _is_weak(cp: dict, rule: dict) -> bool:
    unrealized = cp.get("unrealized_pct")
    if unrealized is None or unrealized > rule["max_unrealized"]:
        return False
    max_rs = rule.get("max_rs")
    if max_rs is None:
        return True
    rs = cp.get("rs_vs_spy")
    return rs is not None and rs <= max_rs


def _early_exit_pnl(trade: dict, checkpoint: dict) -> float:
    exit_price = apply_slippage(checkpoint["close"], SLIPPAGE_BPS_TARGET, "sell")
    shares = trade.get("shares") or 0
    return round(
        (exit_price - trade["entry_price"]) * shares
        - exit_price * ROUND_TRIP_COST_PCT * shares,
        2,
    )


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
            "future_to_actual_exit_return": (
                round((trade["exit_price"] - close) / close, 6)
                if close > 0 else None
            ),
        }
        cp["news_window"] = _news_window(cp["date"], ticker)
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
        "checkpoints": checkpoints,
    }


def _screen(rows: list[dict], baseline_pnl: float) -> dict:
    variants = {}
    for day in CHECKPOINTS:
        for rule_name, rule in WEAK_RULES.items():
            variant = f"d{day}_{rule_name}_and_t1_negative"
            touched = []
            for row in rows:
                cp = row["checkpoints"].get(str(day))
                if not cp or not _is_weak(cp, rule):
                    continue
                if not cp["news_window"]["has_t1_negative"]:
                    continue
                early_pnl = _early_exit_pnl(row, cp)
                touched.append({
                    "ticker": row["ticker"],
                    "strategy": row["strategy"],
                    "sector": row["sector"],
                    "entry_date": row["entry_date"],
                    "checkpoint_date": cp["date"],
                    "actual_exit_date": row["exit_date"],
                    "actual_exit_reason": row["exit_reason"],
                    "actual_pnl": row["actual_pnl"],
                    "early_exit_pnl": early_pnl,
                    "pnl_delta": round(early_pnl - row["actual_pnl"], 2),
                    "checkpoint": cp,
                })
            variants[variant] = {
                "triggered_trades": len(touched),
                "pnl_delta_usd": round(sum(t["pnl_delta"] for t in touched), 2),
                "approx_total_pnl_usd": round(
                    baseline_pnl + sum(t["pnl_delta"] for t in touched),
                    2,
                ),
                "touched": touched,
                "note": "Approximation only; does not replay freed-slot reinvestment.",
            }
    return variants


def _coverage(rows: list[dict]) -> dict:
    cps = []
    weak_cps = 0
    t1_neg_cps = 0
    any_t1_cps = 0
    covered_fraction_sum = 0.0
    for row in rows:
        for cp in row["checkpoints"].values():
            cps.append(cp)
            covered_fraction_sum += cp["news_window"]["coverage_fraction"]
            if cp["news_window"]["has_t1_negative"]:
                t1_neg_cps += 1
            if cp["news_window"]["has_any_t1"]:
                any_t1_cps += 1
            if any(_is_weak(cp, rule) for rule in WEAK_RULES.values()):
                weak_cps += 1
    return {
        "checkpoint_count": len(cps),
        "avg_lookaround_coverage_fraction": (
            round(covered_fraction_sum / len(cps), 4) if cps else None
        ),
        "weak_checkpoint_count": weak_cps,
        "any_t1_checkpoint_count": any_t1_cps,
        "t1_negative_checkpoint_count": t1_neg_cps,
        "weak_and_t1_negative_checkpoint_count": sum(
            1
            for row in rows
            for cp in row["checkpoints"].values()
            if cp["news_window"]["has_t1_negative"]
            and any(_is_weak(cp, rule) for rule in WEAK_RULES.values())
        ),
    }


def _audit_window(label: str, cfg: dict, universe: list[str]) -> dict:
    result, ohlcv = _load_window(universe, cfg)
    rows = []
    for trade in result.get("trades", []):
        item = _audit_trade(trade, ohlcv)
        if item:
            rows.append(item)
    baseline_pnl = result.get("total_pnl") or 0.0
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
        "coverage": _coverage(rows),
        "variants": _screen(rows, baseline_pnl),
        "rows": rows,
    }


def main() -> int:
    universe = get_universe()
    windows = []
    for label, cfg in WINDOWS.items():
        item = _audit_window(label, cfg, universe)
        windows.append(item)
        cov = item["coverage"]
        best = sorted(
            item["variants"].items(),
            key=lambda kv: kv[1]["pnl_delta_usd"],
            reverse=True,
        )[0]
        print(
            f"[{label}] checkpoints={cov['checkpoint_count']} "
            f"coverage={cov['avg_lookaround_coverage_fraction']} "
            f"weak={cov['weak_checkpoint_count']} "
            f"t1neg={cov['t1_negative_checkpoint_count']} "
            f"weak+t1neg={cov['weak_and_t1_negative_checkpoint_count']} "
            f"best={best[0]} delta={best[1]['pnl_delta_usd']} "
            f"triggers={best[1]['triggered_trades']}"
        )
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "experiment_id": "exp-20260425-037",
            "status": "audit_screen_only",
            "hypothesis": (
                "Weak holds require fresh adverse information confirmation; "
                "price weakness alone was rejected in exp-20260425-036."
            ),
            "news_lookaround_days": NEWS_LOOKAROUND_DAYS,
            "weak_rules": WEAK_RULES,
            "windows": windows,
        }, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
