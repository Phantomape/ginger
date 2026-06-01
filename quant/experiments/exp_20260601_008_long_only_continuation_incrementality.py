"""exp-20260601-008: Long-only short-formation continuation -- excess return and
incrementality over core momentum (ret20).

Lane: alpha_discovery.
Change type: read_only_long_only_short_formation_continuation_incrementality.
Single causal variable: ret5_top_quintile_10d_excess_return_incremental_to_ret20.

Why this experiment exists
--------------------------
exp-20260601-007 rejected short-horizon reversal but found an incidental
lead: short-formation (5d) winners continue over a 10-day hold (top
quintile +1.34pct/10d, 3/3 windows, t=2.15). That was flagged NOT-promoted
for four reasons. This experiment is the disciplined follow-up addressing
them:

1. Multiple testing: f5/h10 was selected from a 6-cell grid in exp-007, so
   it inherits that multiple-testing debt. The per-day t-stat is reported
   but is NOT treated as independent confirmation. The load-bearing NEW
   evidence is the ret20 double-sort (item 3).
2. Thin net of cost: this experiment uses a LONG-ONLY frame (one round
   trip, 0.35pct), not a long-short (0.70pct), and measures excess over the
   broad-universe equal-weight mean -- the realistic long-only alpha.
3. Incremental over core momentum: the decisive test. Within ret20
   (core-momentum proxy) quintile bands, does the 5d-formation
   top-minus-bottom forward spread survive a double-sort? If it collapses,
   the short-formation continuation is just the same momentum the core
   already trades; if it survives, it is a distinct short-horizon effect.
4. Horizon-specific: only f5/h10 is examined (pre-registered single cell).

Read-only: changes no entries, exits, ranking, sizing, LLM/news inputs,
paper sleeves, or live orders. Raw close-to-close forward returns, skip-day.

Decision
--------
- ``accepted_incremental_short_formation_continuation`` only if ALL hold:
  (a) long-only top-quintile excess over universe mean > one round-trip
      cost (0.35pct) per 10d hold;
  (b) majority-positive windows for that excess;
  (c) the ret20 double-sort residual top-minus-bottom spread keeps the
      continuation sign and clears the round-trip cost (incremental over
      core momentum).
- ``observed_only_continuation_not_incremental_over_ret20`` if (a)/(b) hold
  but the ret20 double-sort residual collapses (just momentum).
- ``observed_only_no_long_only_excess`` otherwise.

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

try:
    from constants import ROUND_TRIP_COST_PCT
except ImportError:  # pragma: no cover
    from quant.constants import ROUND_TRIP_COST_PCT

EXP_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260601-008"
DEFAULT_OUTPUT = EXP_DIR / "long_only_continuation_incrementality.json"

EXPERIMENT_ID = "exp-20260601-008"
RULE_VERSION = "long_only_short_formation_continuation_incrementality_v1"

WINDOWS = {
    "late_strong": ("2025-10-23", "2026-04-21"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "old_thin": ("2024-10-02", "2025-04-22"),
}

FORMATION = 5      # pre-registered (inherited from exp-007)
CORE_MOMENTUM = 20  # ret20 core-momentum control horizon
HOLD = 10
SKIP_DAYS = 1
QUINTILE = 5
MIN_NAMES_PER_DAY = 50
LONG_ONLY_COST = ROUND_TRIP_COST_PCT  # one round trip (entry+exit) for long-only
T_STAT_FLOOR = 2.0


def _ret(closes: list[float], pos: int, lookback: int) -> float | None:
    j = pos - lookback
    if j < 0:
        return None
    a, b = closes[j], closes[pos]
    if a <= 0 or b <= 0:
        return None
    return b / a - 1.0


def _skip_fwd(closes: list[float], pos: int, hold: int) -> float | None:
    entry = pos + SKIP_DAYS
    exit_ = entry + hold
    if exit_ >= len(closes):
        return None
    ce, cx = closes[entry], closes[exit_]
    if ce <= 0 or cx <= 0:
        return None
    return cx / ce - 1.0


def _prepare(frames: dict[str, pd.DataFrame]) -> dict[str, dict[str, Any]]:
    out = {}
    for t, fr in frames.items():
        out[t] = {
            "closes": [float(x) for x in fr["Close"].tolist()],
            "pos_by_date": {d: i for i, d in enumerate(fr.index)},
            "dates": list(fr.index),
        }
    return out


def _sampled_days(prepared, start, end, step):
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    all_dates: set[pd.Timestamp] = set()
    for p in prepared.values():
        for d in p["dates"]:
            if s <= d <= e:
                all_dates.add(d)
    ordered = sorted(all_dates)
    if not ordered:
        return []
    buffer = SKIP_DAYS + HOLD + 2
    eligible = ordered[:-buffer] if len(ordered) > buffer else []
    return eligible[::step]


def _day_cross_section(prepared, asof) -> list[dict[str, float]]:
    rows = []
    for p in prepared.values():
        pos = p["pos_by_date"].get(asof)
        if pos is None:
            continue
        ret5 = _ret(p["closes"], pos, FORMATION)
        ret20 = _ret(p["closes"], pos, CORE_MOMENTUM)
        fwd = _skip_fwd(p["closes"], pos, HOLD)
        if ret5 is None or ret20 is None or fwd is None:
            continue
        rows.append({"ret5": ret5, "ret20": ret20, "fwd": fwd})
    return rows


def _quintile_groups(rows, key):
    ordered = sorted(rows, key=lambda r: r[key])
    n = len(ordered)
    return [ordered[(i * n) // QUINTILE : ((i + 1) * n) // QUINTILE] for i in range(QUINTILE)]


def _tstat(series):
    if len(series) < 3:
        return None
    sd = statistics.pstdev(series)
    if sd == 0:
        return None
    return round(statistics.mean(series) / (sd / math.sqrt(len(series))), 4)


def run(output: Path = DEFAULT_OUTPUT, *, db_path: Path | None = None) -> dict[str, Any]:
    t0 = time.time()
    frames = load_warehouse_frames(db_path) if db_path else load_warehouse_frames()
    prepared = _prepare(frames)

    # daily series
    excess_series_all: list[float] = []          # top ret5 quintile mean - universe mean
    excess_by_window: dict[str, list[float]] = {}
    resid_series_all: list[float] = []           # ret20-double-sort: ret5 top-bottom within band
    ladder_accum = [[] for _ in range(QUINTILE)]  # pooled ret5 quintile fwd means

    for window, (start, end) in WINDOWS.items():
        days = _sampled_days(prepared, start, end, HOLD)  # non-overlapping
        ex_list = []
        for asof in days:
            rows = _day_cross_section(prepared, asof)
            if len(rows) < MIN_NAMES_PER_DAY:
                continue
            uni_mean = sum(r["fwd"] for r in rows) / len(rows)
            # ret5 quintiles
            q = _quintile_groups(rows, "ret5")
            for qi, g in enumerate(q):
                if g:
                    ladder_accum[qi].append(sum(r["fwd"] for r in g) / len(g))
            top = q[-1]
            top_mean = sum(r["fwd"] for r in top) / len(top)
            ex_list.append(top_mean - uni_mean)
            # ret20 double-sort: within each ret20 band, ret5 top-minus-bottom
            band_spreads = []
            for band in _quintile_groups(rows, "ret20"):
                if len(band) < QUINTILE * 2:
                    continue
                bq = _quintile_groups(band, "ret5")
                bt, bb = bq[-1], bq[0]
                if bt and bb:
                    band_spreads.append(
                        sum(r["fwd"] for r in bt) / len(bt)
                        - sum(r["fwd"] for r in bb) / len(bb)
                    )
            if band_spreads:
                resid_series_all.append(sum(band_spreads) / len(band_spreads))
        excess_by_window[window] = ex_list
        excess_series_all.extend(ex_list)

    excess_mean = statistics.mean(excess_series_all) if excess_series_all else None
    excess_net = (excess_mean - LONG_ONLY_COST) if excess_mean is not None else None
    excess_tstat = _tstat(excess_series_all)
    window_excess = {w: (round(statistics.mean(v), 6) if v else None) for w, v in excess_by_window.items()}
    pos_windows = sum(1 for v in window_excess.values() if v is not None and v > 0)
    meas_windows = sum(1 for v in window_excess.values() if v is not None)

    resid_mean = statistics.mean(resid_series_all) if resid_series_all else None
    resid_tstat = _tstat(resid_series_all)
    ladder = [round(statistics.mean(q), 6) if q else None for q in ladder_accum]

    # judge
    excess_ok = (
        excess_net is not None and excess_net > 0
        and meas_windows > 0 and pos_windows > meas_windows / 2
    )
    # incremental: residual ret5 top-minus-bottom within ret20 bands must keep
    # the continuation sign, clear one round-trip cost, AND be statistically
    # significant (t >= 2). A positive point estimate with an insignificant
    # t-stat does NOT establish incrementality over core momentum.
    incremental_ok = (
        resid_mean is not None
        and resid_mean > LONG_ONLY_COST
        and resid_tstat is not None
        and resid_tstat >= T_STAT_FLOOR
    )

    if excess_ok and incremental_ok:
        status, passed = "accepted_incremental_short_formation_continuation", True
    elif excess_ok and not incremental_ok:
        status, passed = "observed_only_continuation_not_incremental_over_ret20", False
    else:
        status, passed = "observed_only_no_long_only_excess", False

    gates = {
        "gate1": {"name": "cross_section_collected", "passed": bool(excess_series_all),
                  "sampled_days": len(excess_series_all)},
        "gate2": {"name": "skip_day_and_long_only_cost", "passed": True,
                  "skip_days": SKIP_DAYS, "long_only_cost": LONG_ONLY_COST},
        "gate3": {"name": "survival_rate_not_affected_read_only_attribution", "passed": True},
        "gate4": {
            "name": "long_only_excess_and_ret20_incremental",
            "passed": passed,
            "status": status,
            "long_only_top_quintile_excess_gross": round(excess_mean, 6) if excess_mean is not None else None,
            "long_only_top_quintile_excess_net": round(excess_net, 6) if excess_net is not None else None,
            "excess_tstat_inherits_007_multiple_testing_debt": excess_tstat,
            "excess_per_window": window_excess,
            "excess_positive_windows": f"{pos_windows}/{meas_windows}",
            "ret20_double_sort_residual_mean": round(resid_mean, 6) if resid_mean is not None else None,
            "ret20_double_sort_residual_tstat": resid_tstat,
            "one_round_trip_cost": LONG_ONLY_COST,
            "ret5_quintile_fwd_ladder": ladder,
            "decision_rule": (
                "Accept only if (a) long-only top-quintile excess over universe "
                "mean net of one round trip (0.35pct) > 0 with majority-positive "
                "windows AND (b) the ret20 double-sort residual ret5 top-minus-"
                "bottom > one round trip AND is significant (t >= 2) -- a positive "
                "residual point estimate with an insignificant t-stat does NOT "
                "establish incrementality. If (a) holds but (b) fails -> "
                "continuation_not_incremental_over_ret20. Else no_long_only_excess. "
                "The excess t-stat is reported but inherits exp-007 multiple-"
                "testing debt and is not independent confirmation; the ret20 "
                "residual significance is load-bearing."
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
        "pre_registered_cell": {"formation_days": FORMATION, "hold_days": HOLD,
                                "core_momentum_control": CORE_MOMENTUM, "skip_days": SKIP_DAYS},
        "gates": gates,
        "runtime_seconds": round(time.time() - t0, 1),
        "caveat": (
            "f5/h10 cell selection is inherited from exp-20260601-007's 6-cell "
            "grid, so the excess t-stat carries multiple-testing debt and is not "
            "independent confirmation. Warehouse all_windows_full_liquid "
            "survivorship; raw close-to-close; long-only cost is one flat round "
            "trip and ignores impact; the 3 windows are one contiguous 18-month "
            "period, not independent regimes. True confirmation needs forward / "
            "out-of-sample data."
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
        "excess_gross": g4["long_only_top_quintile_excess_gross"],
        "excess_net": g4["long_only_top_quintile_excess_net"],
        "excess_tstat": g4["excess_tstat_inherits_007_multiple_testing_debt"],
        "excess_per_window": g4["excess_per_window"],
        "ret20_residual_mean": g4["ret20_double_sort_residual_mean"],
        "ret20_residual_tstat": g4["ret20_double_sort_residual_tstat"],
        "one_round_trip_cost": g4["one_round_trip_cost"],
        "ret5_quintile_ladder": g4["ret5_quintile_fwd_ladder"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
