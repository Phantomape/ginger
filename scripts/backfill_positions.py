"""Backfill missing fields in data/open_positions.json.

For positions with null target_price/stop_price/opened_by_strategy:
  1. Try matching historical quant_signals_*.json (ticker + entry_price ≈ avg_cost)
  2. Fallback: compute target/stop from current ATR, mark strategy as "legacy"

For positions with null entry_date:
  3. Reverse-engineer from yfinance price history (find close ≈ avg_cost)

Usage:
    python scripts/backfill_positions.py            # write back
    python scripts/backfill_positions.py --dry-run   # preview only
"""

import glob
import json
import os
import sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "quant"))
from constants import ATR_STOP_MULT, ATR_TARGET_MULT, ATR_PERIOD


POSITIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "open_positions.json")
SIGNALS_GLOB   = os.path.join(os.path.dirname(__file__), "..", "data", "quant_signals_*.json")


def _compute_atr(data, period=ATR_PERIOD):
    """Same ATR formula as feature_layer._compute_atr (Wilder's smoothing)."""
    if len(data) < period + 1:
        return None
    high  = data["High"]
    low   = data["Low"]
    close = data["Close"]
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr_series = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    val = atr_series.iloc[-1]
    return round(float(val.item() if hasattr(val, "item") else val), 4)


def _load_signal_index():
    """Build {ticker: best_signal} from all quant_signals_*.json files.

    "Best" = most recent file where ticker appears in the signals array.
    Returns dict of {ticker: {entry_price, target_price, stop_price, strategy, date}}.
    """
    index = {}
    for path in sorted(glob.glob(SIGNALS_GLOB)):
        basename = os.path.basename(path)
        date_str = basename.replace("quant_signals_", "").replace(".json", "")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        for sig in data.get("signals", []):
            ticker = sig.get("ticker")
            if not ticker:
                continue
            index[ticker] = {
                "entry_price":  sig.get("entry_price"),
                "target_price": sig.get("target_price"),
                "stop_price":   sig.get("stop_price"),
                "strategy":     sig.get("strategy"),
                "date":         date_str,
            }
    return index


def _find_entry_date(ticker, avg_cost, lookback_years=2):
    """Find the trading day when close was nearest to avg_cost."""
    end = pd.Timestamp.now()
    start = end - pd.Timedelta(days=lookback_years * 365)
    df = yf.download(ticker, start=start, end=end, progress=False)
    if df is None or df.empty:
        return None, None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df["_diff"] = (df["Close"] - avg_cost).abs()
    best_idx = df["_diff"].idxmin()
    best_close = float(df.loc[best_idx, "Close"].item()
                        if hasattr(df.loc[best_idx, "Close"], "item")
                        else df.loc[best_idx, "Close"])
    pct_diff = abs(best_close - avg_cost) / avg_cost
    confidence = "high" if pct_diff < 0.02 else ("medium" if pct_diff < 0.05 else "low")
    return str(best_idx.date()), confidence


def backfill(dry_run=False):
    with open(POSITIONS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    signal_index = _load_signal_index()
    positions = data.get("positions", [])
    changes = []

    tickers_needing_ohlcv = set()
    for pos in positions:
        if pos.get("target_price") is None or pos.get("stop_price") is None:
            tickers_needing_ohlcv.add(pos["ticker"])
        if pos.get("entry_date") is None:
            tickers_needing_ohlcv.add(pos["ticker"])

    ohlcv_cache = {}
    if tickers_needing_ohlcv:
        print(f"Downloading OHLCV for {len(tickers_needing_ohlcv)} tickers...")
        end = pd.Timestamp.now()
        start = end - pd.Timedelta(days=2 * 365)
        for ticker in tickers_needing_ohlcv:
            try:
                df = yf.download(ticker, start=start, end=end, progress=False)
                if df is not None and not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    ohlcv_cache[ticker] = df
            except Exception as e:
                print(f"  {ticker}: download failed — {e}")

    for pos in positions:
        ticker = pos["ticker"]
        avg_cost = pos.get("avg_cost", 0)
        pos_changes = []

        already_complete = (
            pos.get("target_price") is not None
            and pos.get("stop_price") is not None
            and pos.get("opened_by_strategy") is not None
            and pos.get("entry_date") is not None
        )
        if already_complete:
            changes.append((ticker, "SKIP", "all fields present"))
            continue

        # --- Try signal match ---
        sig = signal_index.get(ticker)
        matched_signal = False
        if sig and sig.get("entry_price") and avg_cost:
            pct = abs(sig["entry_price"] - avg_cost) / avg_cost
            if pct < 0.03:
                matched_signal = True

        if matched_signal:
            if pos.get("target_price") is None and sig.get("target_price"):
                pos["target_price"] = sig["target_price"]
                pos_changes.append(f"target_price={sig['target_price']} (from signal)")
            if pos.get("stop_price") is None and sig.get("stop_price"):
                pos["stop_price"] = sig["stop_price"]
                pos_changes.append(f"stop_price={sig['stop_price']} (from signal)")
            if pos.get("opened_by_strategy") is None and sig.get("strategy"):
                pos["opened_by_strategy"] = sig["strategy"]
                pos_changes.append(f"strategy={sig['strategy']} (from signal)")
            if pos.get("entry_date") is None and sig.get("date"):
                pos["entry_date"] = f"{sig['date'][:4]}-{sig['date'][4:6]}-{sig['date'][6:]}"
                pos_changes.append(f"entry_date={pos['entry_date']} (from signal file date)")
        else:
            # --- Fallback: ATR-based computation ---
            df = ohlcv_cache.get(ticker)
            if df is not None and len(df) > ATR_PERIOD + 1:
                atr = _compute_atr(df)
                if atr and pos.get("target_price") is None:
                    target = round(avg_cost + ATR_TARGET_MULT * atr, 2)
                    pos["target_price"] = target
                    pos_changes.append(f"target_price={target} (avg_cost + {ATR_TARGET_MULT}×ATR={atr})")
                if atr and pos.get("stop_price") is None:
                    stop = round(avg_cost - ATR_STOP_MULT * atr, 2)
                    pos["stop_price"] = stop
                    pos_changes.append(f"stop_price={stop} (avg_cost - {ATR_STOP_MULT}×ATR={atr})")

            if pos.get("opened_by_strategy") is None:
                pos["opened_by_strategy"] = "legacy"
                pos_changes.append("strategy=legacy")

            # --- entry_date from price history ---
            if pos.get("entry_date") is None and df is not None and len(df) > 0:
                df_temp = df.copy()
                df_temp["_diff"] = (df_temp["Close"] - avg_cost).abs()
                best_idx = df_temp["_diff"].idxmin()
                best_close = float(df_temp.loc[best_idx, "Close"].item()
                                   if hasattr(df_temp.loc[best_idx, "Close"], "item")
                                   else df_temp.loc[best_idx, "Close"])
                pct_diff = abs(best_close - avg_cost) / avg_cost if avg_cost else 1.0
                conf = "high" if pct_diff < 0.02 else ("medium" if pct_diff < 0.05 else "low")
                entry_date = str(best_idx.date())
                pos["entry_date"] = entry_date
                pos_changes.append(
                    f"entry_date={entry_date} (close={best_close:.2f}, "
                    f"diff={pct_diff*100:.1f}%, conf={conf})"
                )

        if pos_changes:
            changes.append((ticker, "FILL", "; ".join(pos_changes)))
        else:
            changes.append((ticker, "NOCHANGE", "no null fields to fill"))

    # --- Print report ---
    print(f"\n{'='*75}")
    print(f"  BACKFILL REPORT  {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*75}")
    for ticker, action, detail in changes:
        print(f"  {ticker:<8} [{action:<8}] {detail}")
    print(f"{'='*75}\n")

    if not dry_run:
        with open(POSITIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Written → {POSITIONS_PATH}")
    else:
        print("(dry run — no changes written)")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    backfill(dry_run=dry)
