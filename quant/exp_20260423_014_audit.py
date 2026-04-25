"""exp-20260423-014 trigger-count audit — no strategy logic changed.

Computes the conjunctive stress_strict trigger per trading day on each of the
three fixed OHLCV snapshots used by the accepted A+B baseline:

    stress_strict = breadth_above_200 <= 0.55 AND spy_pct_from_ma <= -0.02

Emits per-window counts to stdout so the plan's abort-if-late-strong-over-10%
gate can be evaluated before any backtest run. Rolled back after measurement.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict

import pandas as pd


WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end":   "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end":   "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end":   "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    }),
])

BREADTH_THRESHOLD = 0.55
SPY_PCT_THRESHOLD = -0.02


def _load_snapshot(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    raw = payload.get("ohlcv")
    if not isinstance(raw, dict):
        raise ValueError(f"Snapshot missing 'ohlcv' dict: {path}")
    ohlcv = {}
    for ticker, rows in raw.items():
        frame = pd.DataFrame(rows)
        if frame.empty:
            continue
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame = frame.set_index("Date").sort_index()
        frame.index.name = None
        ohlcv[ticker] = frame[["Open", "High", "Low", "Close", "Volume"]]
    return ohlcv


def _audit_window(label: str, cfg: dict, repo_root: str) -> dict:
    snapshot_path = os.path.join(repo_root, cfg["snapshot"])
    ohlcv = _load_snapshot(snapshot_path)

    spy = ohlcv.get("SPY")
    if spy is None or spy.empty:
        raise RuntimeError(f"{label}: SPY missing from {cfg['snapshot']}")

    start = pd.Timestamp(cfg["start"])
    end   = pd.Timestamp(cfg["end"])

    # Use SPY's trading days inside the window as the canonical calendar.
    sim_dates = [d for d in spy.index if start <= d <= end]
    spy_close = spy["Close"].astype(float)
    spy_sma200 = spy_close.rolling(window=200, min_periods=200).mean()

    # Pre-compute each ticker's 200-day SMA; store as aligned Series.
    ticker_close = {
        t: df["Close"].astype(float)
        for t, df in ohlcv.items()
    }
    ticker_sma200 = {
        t: c.rolling(window=200, min_periods=200).mean()
        for t, c in ticker_close.items()
    }

    n_days = 0
    n_breadth_weak = 0
    n_spy_weak = 0
    n_stress_strict = 0
    stress_dates: list[str] = []

    missing_spy_sma_days = 0
    for day in sim_dates:
        n_days += 1
        spy_ma = spy_sma200.get(day)
        if spy_ma is None or pd.isna(spy_ma):
            missing_spy_sma_days += 1
            continue
        spy_px = spy_close.loc[day]
        spy_pct_from_ma = (spy_px - spy_ma) / spy_ma

        # Breadth: fraction of tickers whose close > their own 200MA on this day.
        above = 0
        total = 0
        for t, close_series in ticker_close.items():
            if day not in close_series.index:
                continue
            sma = ticker_sma200[t].get(day)
            if sma is None or pd.isna(sma):
                continue
            total += 1
            if close_series.loc[day] > sma:
                above += 1
        if total == 0:
            continue
        breadth_above_200 = above / total

        breadth_weak = breadth_above_200 <= BREADTH_THRESHOLD
        spy_weak = spy_pct_from_ma <= SPY_PCT_THRESHOLD

        if breadth_weak:
            n_breadth_weak += 1
        if spy_weak:
            n_spy_weak += 1
        if breadth_weak and spy_weak:
            n_stress_strict += 1
            stress_dates.append(day.strftime("%Y-%m-%d"))

    return {
        "label": label,
        "start": cfg["start"],
        "end":   cfg["end"],
        "snapshot": cfg["snapshot"],
        "sim_days": n_days,
        "missing_spy_sma_days": missing_spy_sma_days,
        "breadth_weak_days": n_breadth_weak,
        "spy_weak_days": n_spy_weak,
        "stress_strict_days": n_stress_strict,
        "stress_strict_fraction": (
            round(n_stress_strict / n_days, 4) if n_days else None
        ),
        "stress_dates": stress_dates,
    }


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    results = []
    for label, cfg in WINDOWS.items():
        res = _audit_window(label, cfg, repo_root)
        results.append(res)

    print("\nstress_strict trigger audit")
    print("=" * 66)
    print(f"  Rule: breadth_above_200 <= {BREADTH_THRESHOLD} AND "
          f"spy_pct_from_ma <= {SPY_PCT_THRESHOLD:+.2f}")
    print("-" * 66)
    header = f"  {'window':<14} {'days':>5} {'breadth<=T':>12} {'spy<=T':>8} {'STRICT':>8} {'frac':>8}"
    print(header)
    for r in results:
        print(
            f"  {r['label']:<14} {r['sim_days']:>5} "
            f"{r['breadth_weak_days']:>12} {r['spy_weak_days']:>8} "
            f"{r['stress_strict_days']:>8} "
            f"{(r['stress_strict_fraction'] if r['stress_strict_fraction'] is not None else 0)*100:>7.1f}%"
        )
    print("=" * 66)

    late = next(r for r in results if r["label"] == "late_strong")
    if late["stress_strict_fraction"] is not None and late["stress_strict_fraction"] > 0.10:
        print(
            f"\nABORT: late_strong trigger fraction = "
            f"{late['stress_strict_fraction']*100:.1f}% exceeds 10% limit."
        )
        print("Per plan §Contingency: retune thresholds once, not sweep.")
        return 2
    print("\nPROCEED: late_strong trigger fraction is within budget.")

    # Persist structured output so the experiment-log entry can cite exact counts.
    out_path = os.path.join(
        repo_root, "data", "exp_20260423_014_stress_audit.json"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "breadth_above_200_max": BREADTH_THRESHOLD,
                    "spy_pct_from_ma_max": SPY_PCT_THRESHOLD,
                },
                "windows": results,
            },
            f,
            indent=2,
        )
    print(f"Wrote audit -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
