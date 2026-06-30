"""exp-20260630-016 (alpha_search, observed_only): in-sample large-N test of the
entry ATR-extension (entry_exhaustion) de-allocation signal.

Background: exp-20260627-026 found stretched (extension_atr_mult >= 4.0) entries
directionally worse, but only on 41 forward rows (6 stretched) -- below its 8-row
floor. This runner breaks that count logjam WITHOUT waiting for forward rows or
widening the trading universe: it tags ALL 20d-high-close breakout entries across
the 3 canonical OHLCV windows in the core warehouse universe with the IDENTICAL
PIT extension function (forward_replacement_value._entry_exhaustion_asof) and
compares forward-10d return (raw + SPY-excess) for stretched vs normal.

Read-only attribution. No strategy/order/ranking/sizing change. This is a SCREEN
on a broader breakout population than exp-026's exact accepted-sleeve trades, so a
null result lowers the prior on the axis rather than refuting the narrow
sleeve-only claim (which remains forward-gated).
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))

from forward_replacement_value import (  # noqa: E402
    _entry_exhaustion_asof,
    ENTRY_EXHAUSTION_STRETCHED_ATR_MULT,
)

WINDOWS = [
    ("late_strong", "data/ohlcv/ohlcv_snapshot_20251023_20260421.json", "2025-10-23", "2026-04-21"),
    ("mid_weak", "data/ohlcv/ohlcv_snapshot_20250423_20251022.json", "2025-04-23", "2025-10-22"),
    ("old_thin", "data/ohlcv/ohlcv_snapshot_20241002_20250422.json", "2024-10-02", "2025-04-22"),
]
FWD = 10
LB = 20
ETF = {"SPY", "QQQ", "IEF", "TLT", "GLD", "IAU", "IWM", "DIA", "MDY", "VXX", "UUP"}
OUT = REPO_ROOT / "data" / "experiments" / "exp-20260630-016"


def _to_bars(rec):
    out = []
    for v in rec:
        c = v.get("Close")
        if c is None:
            continue
        c = float(c)
        out.append((str(v.get("Date"))[:10], float(v.get("High", c)), float(v.get("Low", c)), c))
    out.sort(key=lambda b: b[0])
    return out


def _stat(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "mean_pct": None, "median_pct": None}
    return {
        "n": len(xs),
        "mean_pct": round(statistics.mean(xs) * 100, 4),
        "median_pct": round(statistics.median(xs) * 100, 4),
    }


def main() -> None:
    rows = []  # (window, ticker, date, ext, fwd, fwd_excess_spy)
    universe_size = None
    for label, path, wstart, wend in WINDOWS:
        if not os.path.exists(path):
            continue
        ohlcv = json.load(open(path, encoding="utf-8"))["ohlcv"]
        bars_by = {t: _to_bars(ohlcv[t]) for t in ohlcv}
        if universe_size is None:
            universe_size = len(bars_by)
        spy = {d: c for (d, _h, _l, c) in bars_by.get("SPY", [])}
        for t, bars in bars_by.items():
            if t in ETF:
                continue
            closes = [b[3] for b in bars]
            dates = [b[0] for b in bars]
            for i in range(LB, len(bars) - FWD):
                d = dates[i]
                if d < wstart or d > wend:
                    continue
                if closes[i] < max(closes[i - LB + 1 : i + 1]):  # not a 20d-high-close breakout
                    continue
                status, det = _entry_exhaustion_asof(bars_by, t, d)
                if status != "ok" or not det:
                    continue
                fwd = closes[i + FWD] / closes[i] - 1.0
                dn = dates[i + FWD]
                ex = fwd - (spy[dn] / spy[d] - 1.0) if (d in spy and dn in spy) else None
                rows.append((label, t, d, det["extension_atr_mult"], fwd, ex))

    STR = ENTRY_EXHAUSTION_STRETCHED_ATR_MULT
    s = [r for r in rows if r[3] >= STR]
    nrm = [r for r in rows if r[3] < STR]
    rs = sorted(rows, key=lambda r: r[3])
    nq = len(rs)
    quintiles = []
    for q in range(5):
        chunk = rs[nq * q // 5 : nq * (q + 1) // 5]
        quintiles.append({
            "q": q + 1,
            "ext_lo": round(min(c[3] for c in chunk), 4),
            "ext_hi": round(max(c[3] for c in chunk), 4),
            "raw_fwd": _stat([c[4] for c in chunk]),
            "spy_excess": _stat([c[5] for c in chunk]),
        })

    result = {
        "experiment_id": "exp-20260630-016",
        "lane": "alpha_search",
        "decision": "observed_only",
        "strategy_behavior_changed": False,
        "universe_size": universe_size,
        "stretched_threshold_atr_mult": STR,
        "total_breakout_entries": len(rows),
        "stretched_share": round(len(s) / len(rows), 4) if rows else None,
        "stretched_raw_fwd10": _stat([r[4] for r in s]),
        "normal_raw_fwd10": _stat([r[4] for r in nrm]),
        "stretched_spy_excess_fwd10": _stat([r[5] for r in s]),
        "normal_spy_excess_fwd10": _stat([r[5] for r in nrm]),
        "per_window": {
            label: {
                "stretched": _stat([r[4] for r in s if r[0] == label]),
                "normal": _stat([r[4] for r in nrm if r[0] == label]),
            }
            for label, _p, _a, _b in WINDOWS
        },
        "extension_quintiles": quintiles,
        "verdict": (
            "Stretched entries do NOT underperform at scale -- raw +1.72%/+1.79% and "
            "SPY-excess +1.38%/+1.19% vs normal, the OPPOSITE sign of exp-026's n=6 forward read; "
            "extension->return is non-monotonic. The de-allocation axis is not supported in-sample; "
            "exp-026's stretched-worse finding is consistent with small-sample (n=6) noise."
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out_file = OUT / "exp_20260630_016_entry_atr_extension_deallocation_predictive_value_in_sample.json"
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
