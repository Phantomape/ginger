"""exp-20260601-009: Overnight vs intraday return decomposition (broad universe).

Lane: alpha_discovery.
Change type: read_only_overnight_intraday_return_decomposition.
Single causal variable: overnight_vs_intraday_return_component_means.

Why this experiment exists
--------------------------
Every cross-sectional OHLCV probe this session reduced to momentum the core
already trades (ranking exp-003/006, reversal 007, continuation 008). The
unified lesson: factor-mining the broad warehouse keeps rediscovering
momentum. This experiment switches MECHANISM entirely -- a time-of-day
structural decomposition, not cross-sectional stock selection.

The overnight-return anomaly: in US equities most of the close-to-close
premium accrues OVERNIGHT (prev_close -> open) while the intraday session
(open -> close) is flat or negative. This is orthogonal to momentum and has
direct relevance to core entry/exit timing (the system enters at next-day
open).

Method (read-only)
------------------
For every (ticker, day) in the broad 1,446-ticker all-windows-full-liquid
universe across the canonical 3 windows:
  - overnight return  = open[t] / close[t-1] - 1
  - intraday return   = close[t] / open[t] - 1
  - close-to-close    = close[t] / close[t-1] - 1  (≈ (1+on)(1+id)-1)
Aggregate by equal-weight daily cross-sectional mean of each component, then
average those daily means across windows. Report t-stats on the daily mean
series (overnight, intraday, and overnight-minus-intraday), per-window means,
and the share of total close-to-close return attributable to overnight.

This is a structural / market-level decomposition, NOT a cross-sectional
selection signal. It changes no entries, exits, ranking, sizing, LLM/news
inputs, paper sleeves, or live orders. Raw prices, no costs.

Decision
--------
- ``accepted_overnight_premium_structure`` if mean overnight return is
  positive with t>=2, majority-positive windows, AND materially larger than
  mean intraday (overnight-minus-intraday t>=2). (Structural acceptance: the
  anomaly is present and robust; it is NOT a tradeable-edge claim, which would
  require an open/close execution and cost study.)
- ``observed_only_no_robust_overnight_structure`` otherwise.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT / "quant"), str(REPO_ROOT / "quant" / "experiments")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from exp_20260601_006_broad_universe_alpha_score_ranking_validation import (  # noqa: E402
    load_warehouse_frames,
)

EXP_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260601-009"
DEFAULT_OUTPUT = EXP_DIR / "overnight_intraday_decomposition.json"

EXPERIMENT_ID = "exp-20260601-009"
RULE_VERSION = "overnight_intraday_decomposition_v1"

WINDOWS = {
    "late_strong": ("2025-10-23", "2026-04-21"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "old_thin": ("2024-10-02", "2025-04-22"),
}

MIN_NAMES_PER_DAY = 50
T_STAT_FLOOR = 2.0
# guard against split / bad-print microstructure: drop |overnight| or |intraday| > 50%
COMPONENT_CLIP = 0.50


def _tstat(series: list[float]) -> float | None:
    if len(series) < 3:
        return None
    sd = statistics.pstdev(series)
    if sd == 0:
        return None
    return round(statistics.mean(series) / (sd / math.sqrt(len(series))), 4)


def _daily_means(frames: dict[str, pd.DataFrame], start: str, end: str) -> list[dict[str, float]]:
    """Per trading day in [start,end]: equal-weight cross-sectional mean of the
    overnight, intraday, and close-to-close components."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    # union of dates
    all_dates: set[pd.Timestamp] = set()
    for fr in frames.values():
        all_dates.update(fr.loc[s:e].index)
    out = []
    for d in sorted(all_dates):
        on_vals, id_vals, cc_vals = [], [], []
        for fr in frames.values():
            pos = fr.index.get_indexer([d])
            i = pos[0]
            if i <= 0:  # need a prior bar for prev_close
                continue
            prev_close = float(fr["Close"].iloc[i - 1])
            open_ = float(fr["Open"].iloc[i])
            close = float(fr["Close"].iloc[i])
            if prev_close <= 0 or open_ <= 0 or close <= 0:
                continue
            on = open_ / prev_close - 1.0
            idr = close / open_ - 1.0
            cc = close / prev_close - 1.0
            if abs(on) > COMPONENT_CLIP or abs(idr) > COMPONENT_CLIP:
                continue  # likely split/bad print
            on_vals.append(on)
            id_vals.append(idr)
            cc_vals.append(cc)
        if len(on_vals) < MIN_NAMES_PER_DAY:
            continue
        out.append({
            "date": str(d.date()),
            "n": len(on_vals),
            "overnight": sum(on_vals) / len(on_vals),
            "intraday": sum(id_vals) / len(id_vals),
            "close_to_close": sum(cc_vals) / len(cc_vals),
        })
    return out


def run(output: Path = DEFAULT_OUTPUT, *, db_path: Path | None = None) -> dict[str, Any]:
    t0 = time.time()
    frames = load_warehouse_frames(db_path) if db_path else load_warehouse_frames()

    per_window_days: dict[str, list[dict[str, float]]] = {}
    for window, (start, end) in WINDOWS.items():
        per_window_days[window] = _daily_means(frames, start, end)

    all_on = [d["overnight"] for w in per_window_days.values() for d in w]
    all_id = [d["intraday"] for w in per_window_days.values() for d in w]
    all_cc = [d["close_to_close"] for w in per_window_days.values() for d in w]
    all_diff = [d["overnight"] - d["intraday"] for w in per_window_days.values() for d in w]

    def _mean(x):
        return round(statistics.mean(x), 6) if x else None

    overnight_mean = _mean(all_on)
    intraday_mean = _mean(all_id)
    cc_mean = _mean(all_cc)
    # share of total close-to-close daily return attributable to overnight
    overnight_share = (
        round(overnight_mean / cc_mean, 4) if (overnight_mean is not None and cc_mean not in (None, 0)) else None
    )
    window_means = {
        w: {
            "overnight": _mean([d["overnight"] for d in days]),
            "intraday": _mean([d["intraday"] for d in days]),
            "n_days": len(days),
        }
        for w, days in per_window_days.items()
    }
    on_pos_windows = sum(1 for v in window_means.values() if v["overnight"] is not None and v["overnight"] > 0)
    meas_windows = sum(1 for v in window_means.values() if v["overnight"] is not None)

    overnight_tstat = _tstat(all_on)
    intraday_tstat = _tstat(all_id)
    diff_tstat = _tstat(all_diff)

    overnight_significant = overnight_tstat is not None and overnight_tstat >= T_STAT_FLOOR
    diff_significant = diff_tstat is not None and diff_tstat >= T_STAT_FLOOR
    majority_windows = meas_windows > 0 and on_pos_windows > meas_windows / 2

    if overnight_significant and majority_windows and diff_significant:
        status, passed = "accepted_overnight_premium_structure", True
    else:
        status, passed = "observed_only_no_robust_overnight_structure", False

    gates = {
        "gate1": {"name": "daily_cross_section_collected", "passed": bool(all_on),
                  "total_days": len(all_on)},
        "gate2": {"name": "component_clip_applied_microstructure_guard", "passed": True,
                  "component_clip": COMPONENT_CLIP, "min_names_per_day": MIN_NAMES_PER_DAY},
        "gate3": {"name": "survival_rate_not_affected_read_only_attribution", "passed": True},
        "gate4": {
            "name": "robust_overnight_premium_vs_intraday",
            "passed": passed,
            "status": status,
            "tstat_floor": T_STAT_FLOOR,
            "overnight_mean_daily": overnight_mean,
            "intraday_mean_daily": intraday_mean,
            "close_to_close_mean_daily": cc_mean,
            "overnight_share_of_close_to_close": overnight_share,
            "overnight_tstat": overnight_tstat,
            "intraday_tstat": intraday_tstat,
            "overnight_minus_intraday_tstat": diff_tstat,
            "overnight_positive_windows": f"{on_pos_windows}/{meas_windows}",
            "per_window": window_means,
            "decision_rule": (
                "Accept the overnight-premium STRUCTURE (not a tradeable edge) "
                "if mean overnight daily return has t>=2, majority-positive "
                "windows, AND overnight-minus-intraday has t>=2. Tradeable-edge "
                "claims would additionally require an open/close execution and "
                "cost study, which this attribution does not perform."
            ),
        },
    }
    gates["all_passed"] = passed

    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "decision": status,
        "universe": "exp-20260519-030 warehouse all_windows_full_liquid",
        "universe_size": len(frames),
        "gates": gates,
        "runtime_seconds": round(time.time() - t0, 1),
        "caveat": (
            "Structural decomposition, not a tradeable edge: capturing the "
            "overnight premium requires buying at/near close and selling at/near "
            "open every day, which incurs heavy turnover cost, spread, and is the "
            "exact regime the overnight anomaly literature debates as hard to "
            "monetize. Warehouse all_windows_full_liquid survivorship; raw prices; "
            "no costs; gap-open microstructure partly mitigated by a 50pct "
            "component clip; the 3 windows are one contiguous 18-month period."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    r = run(args.output)
    g4 = r["gates"]["gate4"]
    print(json.dumps({
        "experiment_id": r["experiment_id"],
        "decision": r["decision"],
        "universe_size": r["universe_size"],
        "runtime_seconds": r["runtime_seconds"],
        "overnight_mean_daily": g4["overnight_mean_daily"],
        "intraday_mean_daily": g4["intraday_mean_daily"],
        "close_to_close_mean_daily": g4["close_to_close_mean_daily"],
        "overnight_share_of_close_to_close": g4["overnight_share_of_close_to_close"],
        "overnight_tstat": g4["overnight_tstat"],
        "intraday_tstat": g4["intraday_tstat"],
        "overnight_minus_intraday_tstat": g4["overnight_minus_intraday_tstat"],
        "overnight_positive_windows": g4["overnight_positive_windows"],
        "per_window": g4["per_window"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
