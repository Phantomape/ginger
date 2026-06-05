"""exp-20260605-010: Broad-universe realized fundamental-growth forward-return
attribution, with a ret20 incrementality control.

Lane: alpha_discovery.
Change type: read_only_broad_universe_realized_fundamental_growth_forward_return.
Single causal variable:
    realized_yoy_growth_quintile_forward_return_incremental_to_ret20.

Why this experiment exists
--------------------------
exp-20260605-007 built a clean, broad, PIT-safe realized-fundamentals asset
(SEC Companyfacts YoY growth for the 1,446 liquid universe), the free
alternative to the sparse/dirty yfinance eps_estimate. This is the first
read-only test of whether that realized growth predicts forward returns on
the broad universe, and -- the decisive question, mirroring exp-20260601-008
-- whether it is INCREMENTAL over ret20 momentum (which the prior
cross-sectional line reduced to). Independent of the FUNDAMENTAL_GROWTH_RS
paper sleeve (different universe, read-only attribution, no sleeve change).

Method (read-only, PIT)
-----------------------
- Signal: for each (signal_day, ticker), the most recent companyfacts
  ``revenue`` YoY growth row with ``asof_date <= signal_day`` and
  ``growth_status == "ok"`` (PIT-safe). EPS growth reported as secondary.
- Forward returns: skip-day (enter T+1) close-to-close at 10d / 20d on the
  warehouse OHLCV.
- Sample every 5th trading day across the canonical 3 windows.
- Bucket by growth quintile; daily long-short (top-minus-bottom) series ->
  t-stat, per-window means, pooled ladder.
- ret20 double-sort: within each ret20 quintile band, growth top-minus-bottom
  20d spread, averaged -> residual + t-stat. A positive residual point
  estimate alone is NOT incrementality; it must be significant (t>=2).

Read-only: changes no entries, exits, ranking, sizing, sleeves, or orders.
Raw close-to-close, no costs in the spread (cost noted in the verdict).

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
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

EXP_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260605-010"
DEFAULT_OUTPUT = EXP_DIR / "broad_fundamental_growth_attribution.json"
GROWTH_PATH = REPO_ROOT / "data" / "kova" / "fundamentals" / "companyfacts_growth_broad_universe_20260604.jsonl"

EXPERIMENT_ID = "exp-20260605-010"
RULE_VERSION = "broad_fundamental_growth_forward_return_v1"

WINDOWS = {
    "late_strong": ("2025-10-23", "2026-04-21"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "old_thin": ("2024-10-02", "2025-04-22"),
}

PRIMARY_CANONICAL = "revenue"
SAMPLE_STEP = 5
SKIP_DAYS = 1
RET20_LOOKBACK = 20
FORWARD_HORIZONS = (10, 20)
PRIMARY_HORIZON = 20
QUINTILE = 5
MIN_NAMES_PER_DAY = 50
T_STAT_FLOOR = 2.0
LONG_SHORT_COST = 2 * ROUND_TRIP_COST_PCT  # 0.70pct per rebalance
# cap growth outliers (companyfacts can have huge YoY on tiny-base prior periods)
GROWTH_CLIP = 5.0  # +/-500% YoY


def load_growth_index(path: Path = GROWTH_PATH, canonical: str = PRIMARY_CANONICAL) -> dict[str, list[tuple[str, float]]]:
    """{ticker: sorted [(asof_date, yoy_growth)]} for ok rows of one canonical."""
    idx: dict[str, list[tuple[str, float]]] = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("canonical") != canonical or r.get("growth_status") != "ok":
                continue
            g = r.get("yoy_growth")
            asof = str(r.get("asof_date") or "")[:10]
            t = str(r.get("ticker") or "").upper()
            if g is None or not asof or not t:
                continue
            try:
                gv = float(g)
            except (TypeError, ValueError):
                continue
            if abs(gv) > GROWTH_CLIP:
                gv = math.copysign(GROWTH_CLIP, gv)
            idx.setdefault(t, []).append((asof, gv))
    for t in idx:
        idx[t].sort()
    return idx


def latest_growth(idx: dict[str, list[tuple[str, float]]], ticker: str, signal_day: str) -> float | None:
    pairs = idx.get(ticker)
    if not pairs:
        return None
    best = None
    for asof, g in pairs:
        if asof <= signal_day:
            best = g
        else:
            break
    return best


def _prepare(frames: dict[str, pd.DataFrame]) -> dict[str, dict[str, Any]]:
    out = {}
    for t, fr in frames.items():
        out[t] = {
            "closes": [float(x) for x in fr["Close"].tolist()],
            "pos_by_date": {d: i for i, d in enumerate(fr.index)},
            "dates": list(fr.index),
        }
    return out


def _ret(closes, pos, lb):
    j = pos - lb
    if j < 0:
        return None
    a, b = closes[j], closes[pos]
    return (b / a - 1.0) if a > 0 and b > 0 else None


def _skip_fwd(closes, pos, hold):
    e = pos + SKIP_DAYS
    x = e + hold
    if x >= len(closes):
        return None
    ce, cx = closes[e], closes[x]
    return (cx / ce - 1.0) if ce > 0 and cx > 0 else None


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
    buffer = SKIP_DAYS + max(FORWARD_HORIZONS) + 2
    return ordered[:-buffer][::step] if len(ordered) > buffer else []


def _tstat(series):
    if len(series) < 3:
        return None
    sd = statistics.pstdev(series)
    if sd == 0:
        return None
    return round(statistics.mean(series) / (sd / math.sqrt(len(series))), 4)


def _quintile_groups(rows, key):
    o = sorted(rows, key=lambda r: r[key])
    n = len(o)
    return [o[(i * n) // QUINTILE:((i + 1) * n) // QUINTILE] for i in range(QUINTILE)]


def collect(prepared, growth_idx, start, end):
    """Per sampled day: rows with {growth, ret20, fwd10, fwd20}; plus daily
    long-short (top-bottom growth quintile) by horizon."""
    obs = []
    daily_ls = {h: [] for h in FORWARD_HORIZONS}
    for asof in _sampled_days(prepared, start, end, SAMPLE_STEP):
        asof_str = str(asof.date())
        day_rows = []
        for t, p in prepared.items():
            pos = p["pos_by_date"].get(asof)
            if pos is None:
                continue
            g = latest_growth(growth_idx, t, asof_str)
            if g is None:
                continue
            r20 = _ret(p["closes"], pos, RET20_LOOKBACK)
            f10 = _skip_fwd(p["closes"], pos, 10)
            f20 = _skip_fwd(p["closes"], pos, 20)
            if r20 is None or f20 is None:
                continue
            day_rows.append({"ticker": t, "growth": g, "ret20": r20, "f10": f10, "f20": f20})
        if len(day_rows) < MIN_NAMES_PER_DAY:
            continue
        obs.extend(day_rows)
        q = _quintile_groups(day_rows, "growth")
        for h, key in ((10, "f10"), (20, "f20")):
            top = [r[key] for r in q[-1] if r[key] is not None]
            bot = [r[key] for r in q[0] if r[key] is not None]
            if top and bot:
                daily_ls[h].append(sum(top) / len(top) - sum(bot) / len(bot))
    return obs, daily_ls


def _pooled_ladder(obs, horizon_key):
    q = _quintile_groups(obs, "growth")
    out = []
    for b in q:
        rets = [r[horizon_key] for r in b if r[horizon_key] is not None]
        out.append(round(sum(rets) / len(rets), 6) if rets else None)
    return out


def _conditional_vs_ret20(obs, horizon_key):
    """growth top-minus-bottom within ret20 quintile bands (double-sort residual)."""
    bands = _quintile_groups(obs, "ret20")
    spreads = []
    for band in bands:
        if len(band) < QUINTILE * 4:
            continue
        gq = _quintile_groups(band, "growth")
        top = [r[horizon_key] for r in gq[-1] if r[horizon_key] is not None]
        bot = [r[horizon_key] for r in gq[0] if r[horizon_key] is not None]
        if len(top) >= 3 and len(bot) >= 3:
            spreads.append(sum(top) / len(top) - sum(bot) / len(bot))
    if not spreads:
        return None, None
    return round(sum(spreads) / len(spreads), 6), _tstat(spreads)


def run(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    import time
    t0 = time.time()
    growth_idx = load_growth_index()
    frames = load_warehouse_frames()
    prepared = _prepare(frames)

    per_window_obs = {}
    per_window_ls = {}
    for w, (s, e) in WINDOWS.items():
        obs, daily_ls = collect(prepared, growth_idx, s, e)
        per_window_obs[w] = obs
        per_window_ls[w] = daily_ls
    pooled = [r for obs in per_window_obs.values() for r in obs]

    # pooled long-short t-stat per horizon (across all sampled days, all windows)
    ls_all = {h: [v for w in per_window_ls.values() for v in w[h]] for h in FORWARD_HORIZONS}
    ls_tstat = {h: _tstat(ls_all[h]) for h in FORWARD_HORIZONS}
    ls_mean = {h: (round(statistics.mean(ls_all[h]), 6) if ls_all[h] else None) for h in FORWARD_HORIZONS}
    window_ls_mean = {
        h: {w: (round(statistics.mean(per_window_ls[w][h]), 6) if per_window_ls[w][h] else None)
            for w in WINDOWS}
        for h in FORWARD_HORIZONS
    }
    pos_windows = {
        h: sum(1 for v in window_ls_mean[h].values() if v is not None and v > 0)
        for h in FORWARD_HORIZONS
    }
    ladders = {h: _pooled_ladder(pooled, "f10" if h == 10 else "f20") for h in FORWARD_HORIZONS}
    resid_mean, resid_tstat = _conditional_vs_ret20(pooled, "f20")

    # judge on primary horizon (20d)
    h = PRIMARY_HORIZON
    raw_ok = (
        ls_mean[h] is not None and ls_mean[h] > 0
        and ls_tstat[h] is not None and ls_tstat[h] >= T_STAT_FLOOR
        and pos_windows[h] > len(WINDOWS) / 2
    )
    raw_net_ok = ls_mean[h] is not None and (ls_mean[h] - LONG_SHORT_COST) > 0
    incremental_ok = (
        resid_mean is not None and resid_mean > LONG_SHORT_COST
        and resid_tstat is not None and resid_tstat >= T_STAT_FLOOR
    )
    inverted = ls_mean[h] is not None and ls_mean[h] <= -LONG_SHORT_COST and ls_tstat[h] is not None and ls_tstat[h] <= -T_STAT_FLOOR

    if raw_ok and raw_net_ok and incremental_ok:
        status, passed = "accepted_incremental_fundamental_growth_edge", True
    elif raw_ok and not incremental_ok:
        status, passed = "observed_only_growth_not_incremental_over_ret20", False
    elif inverted:
        status, passed = "rejected_fundamental_growth_inverted", False
    else:
        status, passed = "observed_only_no_robust_growth_edge", False

    payload = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "decision": status,
        "universe": "exp-20260519-030 warehouse all_windows_full_liquid",
        "signal": f"companyfacts {PRIMARY_CANONICAL} YoY growth (PIT asof<=signal_day), clip +/-{GROWTH_CLIP}",
        "total_observations": len(pooled),
        "observations_by_window": {w: len(o) for w, o in per_window_obs.items()},
        "growth_quintile_long_short": {
            f"h{h_}": {
                "mean_gross": ls_mean[h_],
                "mean_net_of_cost": (round(ls_mean[h_] - LONG_SHORT_COST, 6) if ls_mean[h_] is not None else None),
                "tstat": ls_tstat[h_],
                "per_window_mean": window_ls_mean[h_],
                "positive_windows": f"{pos_windows[h_]}/{len(WINDOWS)}",
                "pooled_quintile_ladder_low_to_high_growth": ladders[h_],
            }
            for h_ in FORWARD_HORIZONS
        },
        "ret20_double_sort_residual_20d": {
            "mean": resid_mean, "tstat": resid_tstat,
            "note": "growth top-minus-bottom within ret20 bands; must be >cost AND t>=2 for incrementality",
        },
        "round_trip_long_short_cost": LONG_SHORT_COST,
        "tstat_floor": T_STAT_FLOOR,
        "gates": {
            "gate1": {"name": "observations_collected", "passed": len(pooled) > 0, "n": len(pooled)},
            "gate2": {"name": "pit_growth_join", "passed": True,
                      "note": "signal uses most recent companyfacts row with asof_date<=signal_day"},
            "gate3": {"name": "survival_rate_not_affected_read_only", "passed": True},
            "gate4": {"name": "incremental_growth_edge_over_ret20", "passed": passed, "status": status,
                      "primary_horizon": PRIMARY_HORIZON,
                      "raw_long_short_ok": raw_ok, "raw_net_of_cost_ok": raw_net_ok,
                      "incremental_over_ret20": incremental_ok,
                      "residual_mean": resid_mean, "residual_tstat": resid_tstat},
            "all_passed": passed,
        },
        "runtime_seconds": round(time.time() - t0, 1),
        "caveat": (
            "Realized (not forward) growth; quarterly value held constant between "
            "filings so daily-frequency signal is stale within a quarter. Warehouse "
            "survivorship; raw close-to-close; growth clipped at +/-500pct YoY to "
            "tame tiny-prior-base blowups; 3 windows are one contiguous 18-month "
            "period. Long-short t-stat does not account for borrow/impact."
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
    print(json.dumps({
        "experiment_id": r["experiment_id"], "decision": r["decision"],
        "total_observations": r["total_observations"], "runtime_seconds": r["runtime_seconds"],
        "growth_quintile_long_short": r["growth_quintile_long_short"],
        "ret20_double_sort_residual_20d": r["ret20_double_sort_residual_20d"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
