"""exp-20260425-038 sector-confirmed weak-hold audit.

Hypothesis:
    Price-only weak-hold exits were rejected because weak starts can become
    delayed winners. News-confirmed exits were blocked by sparse archives.
    A deterministic alternative is to require both position weakness and
    sector-level weakness. If the whole sleeve is deteriorating, early capital
    release may be less likely to kill idiosyncratic delayed winners.

Audit/screen only. It estimates trade-level early exits and does not model
freed-slot reinvestment or production equity-curve effects.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict
from statistics import median

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_slippage  # noqa: E402
from portfolio_engine import ROUND_TRIP_COST_PCT  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


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
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260425_038_sector_confirmed_weak_hold_audit.json",
)


VARIANTS = OrderedDict([
    ("d5_stock_neg_rs_lag2_sector_neg", {
        "day": 5,
        "max_unrealized": 0.0,
        "max_stock_rs": -0.02,
        "max_sector_ret": 0.0,
        "max_sector_rs": None,
    }),
    ("d5_stock_neg_rs_lag2_sector_lag2", {
        "day": 5,
        "max_unrealized": 0.0,
        "max_stock_rs": -0.02,
        "max_sector_ret": None,
        "max_sector_rs": -0.02,
    }),
    ("d5_loss_gt3_sector_neg", {
        "day": 5,
        "max_unrealized": -0.03,
        "max_stock_rs": None,
        "max_sector_ret": 0.0,
        "max_sector_rs": None,
    }),
    ("d10_stock_neg_rs_lag2_sector_neg", {
        "day": 10,
        "max_unrealized": 0.0,
        "max_stock_rs": -0.02,
        "max_sector_ret": 0.0,
        "max_sector_rs": None,
    }),
    ("d10_loss_gt3_sector_neg", {
        "day": 10,
        "max_unrealized": -0.03,
        "max_stock_rs": None,
        "max_sector_ret": 0.0,
        "max_sector_rs": None,
    }),
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


def _sector_median_return(ohlcv: dict, sector: str, entry_date: str,
                          checkpoint_date: str, exclude_ticker: str):
    values = []
    for ticker, mapped_sector in SECTOR_MAP.items():
        if mapped_sector != sector or ticker == exclude_ticker:
            continue
        df = ohlcv.get(ticker)
        if df is None:
            continue
        start_idx = _date_index_after(df, entry_date)
        end_idx = _date_index_after(df, checkpoint_date)
        if start_idx is None or end_idx is None or end_idx <= start_idx:
            continue
        value = _return(df, start_idx, end_idx)
        if value is not None:
            values.append(value)
    return {
        "sector_peer_count": len(values),
        "sector_median_return": round(median(values), 6) if values else None,
    }


def _early_exit_pnl(trade: dict, checkpoint: dict) -> float:
    exit_price = apply_slippage(checkpoint["close"], SLIPPAGE_BPS_TARGET, "sell")
    shares = trade.get("shares") or 0
    return round(
        (exit_price - trade["entry_price"]) * shares
        - exit_price * ROUND_TRIP_COST_PCT * shares,
        2,
    )


def _rule_match(cp: dict, rule: dict) -> bool:
    unrealized = cp.get("unrealized_pct")
    if unrealized is None or unrealized > rule["max_unrealized"]:
        return False
    max_stock_rs = rule.get("max_stock_rs")
    if max_stock_rs is not None:
        stock_rs = cp.get("rs_vs_spy")
        if stock_rs is None or stock_rs > max_stock_rs:
            return False
    max_sector_ret = rule.get("max_sector_ret")
    if max_sector_ret is not None:
        sector_ret = cp.get("sector_median_return")
        if sector_ret is None or sector_ret > max_sector_ret:
            return False
    max_sector_rs = rule.get("max_sector_rs")
    if max_sector_rs is not None:
        sector_rs = cp.get("sector_rs_vs_spy")
        if sector_rs is None or sector_rs > max_sector_rs:
            return False
    return True


def _audit_trade(trade: dict, ohlcv: dict) -> dict | None:
    ticker = trade.get("ticker")
    sector = trade.get("sector")
    df = ohlcv.get(ticker)
    spy = ohlcv.get("SPY")
    if df is None or spy is None or not sector:
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
        checkpoint_date = str(df.index[idx].date())
        ticker_ret = _return(df, entry_idx, idx)
        spy_ret = _return(spy, spy_entry_idx, spy_idx)
        sector_stats = _sector_median_return(
            ohlcv,
            sector,
            trade.get("entry_date"),
            checkpoint_date,
            ticker,
        )
        sector_ret = sector_stats["sector_median_return"]
        cp = {
            "date": checkpoint_date,
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
            "sector_peer_count": sector_stats["sector_peer_count"],
            "sector_median_return": sector_ret,
            "sector_rs_vs_spy": (
                round(sector_ret - spy_ret, 6)
                if sector_ret is not None and spy_ret is not None else None
            ),
            "future_to_actual_exit_return": (
                round((trade["exit_price"] - close) / close, 6)
                if close > 0 else None
            ),
        }
        checkpoints[str(day)] = cp

    if not checkpoints:
        return None
    return {
        "ticker": ticker,
        "strategy": trade.get("strategy"),
        "sector": sector,
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
    out = {}
    for name, rule in VARIANTS.items():
        day = str(rule["day"])
        touched = []
        for row in rows:
            cp = row["checkpoints"].get(day)
            if not cp or not _rule_match(cp, rule):
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
        delta = sum(t["pnl_delta"] for t in touched)
        out[name] = {
            "triggered_trades": len(touched),
            "pnl_delta_usd": round(delta, 2),
            "approx_total_pnl_usd": round(baseline_pnl + delta, 2),
            "touched": touched,
            "note": "Approximation only; does not replay freed-slot reinvestment.",
        }
    return out


def _coverage(rows: list[dict]) -> dict:
    checkpoint_count = 0
    with_sector = 0
    weak = 0
    sector_confirmed = 0
    for row in rows:
        for cp in row["checkpoints"].values():
            checkpoint_count += 1
            if cp.get("sector_peer_count", 0) > 0:
                with_sector += 1
            if cp.get("unrealized_pct") is not None and cp["unrealized_pct"] <= 0:
                weak += 1
            if (
                cp.get("unrealized_pct") is not None
                and cp["unrealized_pct"] <= 0
                and cp.get("sector_median_return") is not None
                and cp["sector_median_return"] <= 0
            ):
                sector_confirmed += 1
    return {
        "checkpoint_count": checkpoint_count,
        "sector_available_count": with_sector,
        "weak_checkpoint_count": weak,
        "weak_and_sector_negative_count": sector_confirmed,
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
            f"sector_avail={cov['sector_available_count']} "
            f"weak={cov['weak_checkpoint_count']} "
            f"weak+sector_neg={cov['weak_and_sector_negative_count']} "
            f"best={best[0]} delta={best[1]['pnl_delta_usd']} "
            f"triggers={best[1]['triggered_trades']}"
        )
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "experiment_id": "exp-20260425-038",
            "status": "audit_screen_only",
            "hypothesis": (
                "Weak holds may only be actionable when sector peers confirm "
                "deterioration; price-only weak-hold exits were rejected."
            ),
            "variants": VARIANTS,
            "windows": windows,
        }, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
