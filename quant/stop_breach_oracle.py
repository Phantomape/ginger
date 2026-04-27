"""Observation-only oracle for stop-breach entry cancellations.

When next open is already below the precomputed stop, the backtester cancels
entry. This diagnostic asks a narrower counterfactual: if the trade were
entered at that open and a fresh ATR stop/target were anchored there, what
would have happened over the forward window?
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from constants import ATR_STOP_MULT, ATR_TARGET_MULT, ROUND_TRIP_COST_PCT  # noqa: E402


def _load_json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def infer_snapshot_path(backtest_result):
    known = backtest_result.get("known_biases") or {}
    source = known.get("ohlcv_source") or {}
    return source.get("snapshot_path")


def _ohlcv_rows_by_date(snapshot):
    rows_by_ticker = {}
    for ticker, rows in (snapshot.get("ohlcv") or {}).items():
        rows_by_ticker[ticker.upper()] = {
            row.get("Date"): row
            for row in rows or []
            if row.get("Date")
        }
    return rows_by_ticker


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rows_after(rows_by_date, date_str, horizon_days):
    days = [day for day in sorted(rows_by_date) if day >= date_str]
    return [rows_by_date[day] for day in days[:horizon_days]]


def _atr_before(rows_by_date, date_str, period=14):
    rows = [rows_by_date[day] for day in sorted(rows_by_date) if day <= date_str]
    if len(rows) < period + 1:
        return None
    true_ranges = []
    for idx in range(len(rows) - period, len(rows)):
        row = rows[idx]
        prev = rows[idx - 1]
        high = _safe_float(row.get("High"))
        low = _safe_float(row.get("Low"))
        prev_close = _safe_float(prev.get("Close"))
        if high is None or low is None or prev_close is None:
            return None
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return sum(true_ranges) / len(true_ranges)


def _simulate_reanchored_trade(entry_open, rows, atr):
    stop = entry_open - ATR_STOP_MULT * atr
    target = entry_open + ATR_TARGET_MULT * atr
    for row in rows:
        low = _safe_float(row.get("Low"))
        high = _safe_float(row.get("High"))
        open_ = _safe_float(row.get("Open"))
        if low is None or high is None or open_ is None:
            continue
        if low <= stop:
            exit_raw = open_ if open_ < stop else stop
            exit_price = exit_raw * (1 - ROUND_TRIP_COST_PCT)
            return {
                "exit_date": row.get("Date"),
                "exit_reason": "stop",
                "exit_price": round(exit_price, 4),
                "return_pct": round((exit_price / entry_open) - 1, 6),
            }
        if high >= target:
            exit_raw = open_ if open_ >= target else target
            exit_price = exit_raw * (1 - ROUND_TRIP_COST_PCT)
            return {
                "exit_date": row.get("Date"),
                "exit_reason": "target",
                "exit_price": round(exit_price, 4),
                "return_pct": round((exit_price / entry_open) - 1, 6),
            }
    if not rows:
        return None
    last = rows[-1]
    close = _safe_float(last.get("Close"))
    if close is None:
        return None
    exit_price = close * (1 - ROUND_TRIP_COST_PCT)
    return {
        "exit_date": last.get("Date"),
        "exit_reason": "horizon_end",
        "exit_price": round(exit_price, 4),
        "return_pct": round((exit_price / entry_open) - 1, 6),
    }


def build_stop_breach_oracle(backtest_result, snapshot, horizon_days=20):
    events = (backtest_result.get("entry_execution_attribution") or {}).get("sample_skips") or []
    rows_by_ticker = _ohlcv_rows_by_date(snapshot)
    rows = []
    missing = []
    for event in events:
        if event.get("decision") != "stop_breach_cancel":
            continue
        ticker = (event.get("ticker") or "").upper()
        details = event.get("details") or {}
        fill_date = details.get("fill_date")
        fill_price = _safe_float(details.get("fill_price"))
        ticker_rows = rows_by_ticker.get(ticker)
        if not ticker_rows or not fill_date or fill_price is None:
            missing.append({**event, "missing_reason": "missing_event_or_ohlcv"})
            continue
        atr = _atr_before(ticker_rows, event.get("date"))
        if atr is None:
            missing.append({**event, "missing_reason": "missing_atr"})
            continue
        forward = _rows_after(ticker_rows, fill_date, horizon_days)
        sim = _simulate_reanchored_trade(fill_price, forward, atr)
        if sim is None:
            missing.append({**event, "missing_reason": "simulation_failed"})
            continue
        rows.append({
            "date": event.get("date"),
            "ticker": ticker,
            "strategy": event.get("strategy"),
            "candidate_rank": event.get("candidate_rank"),
            "entry_date": fill_date,
            "entry_open": round(fill_price, 4),
            "old_stop_price": details.get("stop_price"),
            "reanchored_stop_price": round(fill_price - ATR_STOP_MULT * atr, 4),
            "reanchored_target_price": round(fill_price + ATR_TARGET_MULT * atr, 4),
            **sim,
        })

    returns = [row["return_pct"] for row in rows]
    return {
        "oracle_type": "stop_breach_reanchored_entry",
        "is_tradable": False,
        "lookahead_warning": (
            "Uses historical forward OHLCV to test a re-anchored stop/target "
            "counterfactual. This is not a production rule."
        ),
        "horizon_days": horizon_days,
        "sample_count": len(rows),
        "missing_count": len(missing),
        "positive_fraction": (
            round(sum(1 for r in returns if r > 0) / len(returns), 4)
            if returns else None
        ),
        "avg_return_pct": round(sum(returns) / len(returns), 6) if returns else None,
        "best_return_pct": round(max(returns), 6) if returns else None,
        "worst_return_pct": round(min(returns), 6) if returns else None,
        "rows": sorted(rows, key=lambda row: row["return_pct"], reverse=True),
        "missing": missing,
    }


def build_stop_breach_diagnostics(backtest_path, snapshot_path=None, horizon_days=20):
    backtest = _load_json(backtest_path)
    snapshot_path = snapshot_path or infer_snapshot_path(backtest)
    if not snapshot_path:
        raise ValueError("No OHLCV snapshot path found; pass --snapshot explicitly.")
    snapshot = _load_json(snapshot_path)
    return {
        "source_backtest": os.path.abspath(backtest_path),
        "source_snapshot": os.path.abspath(snapshot_path),
        "period": backtest.get("period"),
        "stop_breach_oracle": build_stop_breach_oracle(
            backtest,
            snapshot,
            horizon_days=horizon_days,
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backtest", required=True)
    parser.add_argument("--snapshot")
    parser.add_argument("--horizon-days", type=int, default=20)
    parser.add_argument("--out")
    args = parser.parse_args()

    result = build_stop_breach_diagnostics(
        args.backtest,
        args.snapshot,
        horizon_days=args.horizon_days,
    )
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
